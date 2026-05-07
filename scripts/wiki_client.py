"""BWIKI Semantic MediaWiki API 客户端。"""
from __future__ import annotations

import re
import time
import json
import logging
from typing import Dict, List, Optional
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from urllib.parse import quote, urlencode

log = logging.getLogger(__name__)

_BASE_URL = "https://wiki.biligame.com/rocom/api.php"
_DELAY = 1.5  # 秒，请求间隔
_TIMEOUT = 15
_RETRIES = 3


def _api_get(params: Dict[str, str]) -> dict:
    """发送 GET 请求到 BWIKI API，带重试。URL 编码中文参数。"""
    qs = "&".join(f"{k}={quote(str(v), safe='')}" for k, v in params.items())
    url = f"{_BASE_URL}?{qs}"
    for attempt in range(1, _RETRIES + 1):
        try:
            req = Request(url, headers={"User-Agent": "roco-helper/2.0"})
            with urlopen(req, timeout=_TIMEOUT) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (URLError, HTTPError, TimeoutError) as e:
            log.warning("请求失败 (%d/%d): %s - %s", attempt, _RETRIES, url[:80], e)
            if attempt == _RETRIES:
                raise
            time.sleep(2)


def fetch_all_pets() -> List[dict]:
    """分页拉取全部精灵列表（SMW 批量查询）。"""
    query_base = (
        "[[分类:精灵]]"
        "|?精灵名称|?主属性|?2属性|?精灵序号"
        "|?生命|?速度|?物攻|?魔攻|?物防|?魔防"
        "|?精灵阶段|?特性"
    )
    results = []
    offset = 0
    page = 0
    while True:
        page += 1
        params = {
            "action": "ask",
            "format": "json",
            "query": f"{query_base}|offset={offset}|limit=50",
        }
        data = _api_get(params)
        batch = data.get("query", {}).get("results", {})
        if not batch:
            break
        for name, entry in batch.items():
            po = entry.get("printouts", {})
            results.append({
                "wiki_name": name,
                "精灵名称": _first(po.get("精灵名称", [])),
                "主属性": _first(po.get("主属性", [])),
                "2属性": _first(po.get("2属性", [])),
                "精灵序号": _first(po.get("精灵序号", [])),
                "生命": _first(po.get("生命", [])),
                "速度": _first(po.get("速度", [])),
                "物攻": _first(po.get("物攻", [])),
                "魔攻": _first(po.get("魔攻", [])),
                "物防": _first(po.get("物防", [])),
                "魔防": _first(po.get("魔防", [])),
                "精灵阶段": _first(po.get("精灵阶段", [])),
                "特性": _first(po.get("特性", [])),
            })
        next_offset = data.get("query-continue-offset")
        if next_offset is None or len(batch) < 50:
            break
        offset = next_offset
        time.sleep(_DELAY)
    log.info("拉取精灵列表完成: %d 条, %d 页", len(results), page)
    return results


def fetch_all_skills() -> List[dict]:
    """分页拉取全部技能列表。"""
    query_base = (
        "[[分类:技能]]"
        "|?技能名称|?属性|?威力|?技能类型|?PP|?技能描述"
    )
    results = []
    offset = 0
    page = 0
    while True:
        page += 1
        params = {
            "action": "ask",
            "format": "json",
            "query": f"{query_base}|offset={offset}|limit=50",
        }
        data = _api_get(params)
        batch = data.get("query", {}).get("results", {})
        if not batch:
            break
        for name, entry in batch.items():
            po = entry.get("printouts", {})
            results.append({
                "wiki_name": name,
                "技能名称": _first(po.get("技能名称", [])),
                "属性": _first(po.get("属性", [])),
                "威力": _first(po.get("威力", [])),
                "技能类型": _first(po.get("技能类型", [])),
                "PP": _first(po.get("PP", [])),
                "技能描述": _first(po.get("技能描述", [])),
            })
        next_offset = data.get("query-continue-offset")
        if next_offset is None or len(batch) < 50:
            break
        offset = next_offset
        time.sleep(_DELAY)
    log.info("拉取技能列表完成: %d 条, %d 页", len(results), page)
    return results


def fetch_pet_detail(wiki_name: str) -> Optional[dict]:
    """拉取单只精灵的详情页，解析 {{精灵信息|...}} 模板。"""
    from urllib.parse import quote
    params = {
        "action": "parse",
        "page": wiki_name,
        "prop": "wikitext",
        "format": "json",
    }
    try:
        data = _api_get(params)
    except Exception as e:
        log.warning("拉取精灵详情失败: %s - %s", wiki_name, e)
        return None
    wikitext = data.get("parse", {}).get("wikitext", {}).get("*", "")
    if not wikitext:
        return None
    return _parse_pet_template(wikitext)


def fetch_pet_details(pets: List[dict], skip: bool = False) -> Dict[str, dict]:
    """批量拉取精灵详情。返回 {wiki_name: detail_dict}。"""
    if skip:
        return {}
    details = {}
    total = len(pets)
    for i, pet in enumerate(pets):
        name = pet["wiki_name"]
        if (i + 1) % 50 == 1:
            log.info("拉取精灵详情: %d/%d ...", i + 1, total)
        detail = fetch_pet_detail(name)
        if detail:
            details[name] = detail
        time.sleep(_DELAY)
    log.info("拉取精灵详情完成: %d/%d 成功", len(details), total)
    return details


_TEMPLATE_RE = re.compile(r"\{\{精灵信息\|(.*?)\}\}", re.DOTALL)


def _parse_pet_template(wikitext: str) -> Optional[dict]:
    """解析 {{精灵信息|key=value|...}} 模板为 dict。"""
    m = _TEMPLATE_RE.search(wikitext)
    if not m:
        return None
    body = m.group(1)
    result = {}
    for part in body.split("|"):
        part = part.strip()
        if "=" not in part:
            continue
        key, _, value = part.partition("=")
        result[key.strip()] = value.strip()
    return result


def _first(lst: list) -> str:
    """取列表第一个元素，空则返回空字符串。"""
    return lst[0] if lst else ""
