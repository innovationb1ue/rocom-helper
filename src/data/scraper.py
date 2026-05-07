"""Wiki 爬虫 — 从 Bilibili Wiki 抓取精灵/技能数据。"""
from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_CACHE_DIR = _PROJECT_ROOT / "data" / "cache"
_BASE_URL = "https://wiki.biligame.com/rocom"

_HEADERS = {
    "User-Agent": "RocoPvPHelper/1.0 (wiki scraper; educational use)",
    "Accept": "text/html",
}


class WikiScraper:
    def __init__(self, cache_dir: Optional[Path] = None) -> None:
        if not HAS_HTTPX or not HAS_BS4:
            raise RuntimeError("需要 httpx 和 beautifulsoup4: pip install httpx beautifulsoup4")
        self.cache_dir = cache_dir or _CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.client = httpx.Client(headers=_HEADERS, timeout=30.0, follow_redirects=True)

    def scrape_pet_list(self) -> List[Dict[str, Any]]:
        """从精灵图鉴页面获取精灵列表。"""
        url = f"{_BASE_URL}/%E7%B2%BE%E7%81%B5%E5%9B%BE%E9%89%B4"
        resp = self.client.get(url)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        pets = []
        for link in soup.select("a[href*='/rocom/']"):
            href = link.get("href", "")
            title = link.get("title", "").strip()
            if title and "精灵" not in title and len(title) >= 2:
                pets.append({"name": title, "url": href})
        return pets

    def scrape_pet_detail(self, url: str) -> Dict[str, Any]:
        """从精灵详情页提取数据。"""
        full_url = url if url.startswith("http") else f"{_BASE_URL}{url}"
        resp = self.client.get(full_url)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        result: Dict[str, Any] = {}

        # Extract name from title
        title_el = soup.select_one("#firstHeading")
        if title_el:
            result["name"] = title_el.get_text(strip=True)

        # Try to find stats table
        for table in soup.select("table"):
            rows = table.select("tr")
            for row in rows:
                cells = row.select("td, th")
                if len(cells) >= 2:
                    key = cells[0].get_text(strip=True)
                    val = cells[1].get_text(strip=True)
                    if "属性" in key:
                        result["types_raw"] = val
                    elif "生命" in key or "HP" in key.upper():
                        try:
                            result["hp"] = int(re.search(r"\d+", val).group())
                        except (AttributeError, ValueError):
                            pass
                    elif "攻击" in key:
                        try:
                            result["attack"] = int(re.search(r"\d+", val).group())
                        except (AttributeError, ValueError):
                            pass
                    elif "防御" in key:
                        try:
                            result["defense"] = int(re.search(r"\d+", val).group())
                        except (AttributeError, ValueError):
                            pass
                    elif "速度" in key:
                        try:
                            result["speed"] = int(re.search(r"\d+", val).group())
                        except (AttributeError, ValueError):
                            pass
        return result

    def scrape_type_chart(self) -> Dict[str, Any]:
        """从克制计算器页面提取属性克制矩阵。"""
        url = f"{_BASE_URL}/%E5%85%8B%E5%88%B6%E8%AE%A1%E7%AE%97%E5%99%A8"
        try:
            resp = self.client.get(url)
            resp.raise_for_status()
        except httpx.HTTPStatusError:
            logger.warning("克制计算器页面不可用，返回空数据")
            return {"chart": {}}

        return {"source": url, "scraped_at": time.time()}

    def run_full_scrape(self) -> None:
        """执行完整爬取，保存缓存。"""
        logger.info("开始完整爬取...")

        logger.info("获取精灵列表...")
        pets = self.scrape_pet_list()
        logger.info("找到 %d 个精灵", len(pets))

        self._save_cache("wiki_pets.json", {"pets": pets, "count": len(pets)})

        # Scrape first 20 pets as sample
        details = []
        for i, pet in enumerate(pets[:20]):
            try:
                logger.info("  抓取 %s (%d/%d)", pet["name"], i + 1, min(20, len(pets)))
                detail = self.scrape_pet_detail(pet["url"])
                detail["source_url"] = pet["url"]
                details.append(detail)
                time.sleep(1.0)
            except Exception as e:
                logger.warning("  跳过 %s: %s", pet["name"], e)

        self._save_cache("wiki_pet_details.json", {"pets": details, "count": len(details)})

        meta = {
            "scraped_at": time.time(),
            "pet_count": len(pets),
            "detail_count": len(details),
        }
        self._save_cache("wiki_meta.json", meta)
        logger.info("爬取完成: %d 精灵, %d 详情", len(pets), len(details))

    def load_cached(self, filename: str = "wiki_meta.json") -> Optional[Dict]:
        """加载缓存数据。"""
        path = self.cache_dir / filename
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return None

    def _save_cache(self, filename: str, data: Any) -> None:
        path = self.cache_dir / filename
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.debug("缓存已保存: %s", path)
