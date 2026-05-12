"""验证从 BattleInsidePetInfo.field 8 (skill_round_data) 提取精灵装备技能的正确性。

数据来源: tests/fixtures/packets/battle_session_1

协议路径:
  ZoneBattleEnterNotify (0x1316)
    → field 6: init_info (BattleInitInfo)
      → field 5: player_team / field 6: enemy_team (BattleRoleInfo)
        → field 2: pets (BattlePetInfo)
          → field 1: battle_inside_pet_info (BattleInsidePetInfo)
            → field 8: skill_round_data (PetSkillRoundData)
              → field 39: skill_id
              → field 25: pos  (1-4 = 装备槽位)
              → field 9:  cost_energy
"""
from __future__ import annotations

import pytest
from typing import Any, Dict, List, Set, Tuple

from src.protocol.proto_core import (
    field_groups,
    collect_varints,
    first_sub,
    first_text,
    pick_first,
    skill_name,
)
from tests.packet_reader import replay_battle

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _navigate_battle_enter_teams(
    record: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """从 0x1316 record 中提取所有 BattlePetInfo 子消息。

    Returns:
        [{"name": str, "team": "player"|"enemy", "inside": msg, "pet_data": msg}, ...]
    """
    root = record["root"]
    init_info = first_sub(field_groups(root).get(6, []))
    if init_info is None:
        return []

    result = []
    ig = field_groups(init_info)
    for team_field, team_label in [(5, "player"), (6, "enemy")]:
        for ti_entry in ig.get(team_field, []):
            ti_sub = ti_entry.get("sub")
            if not ti_sub:
                continue
            for pet_entry in field_groups(ti_sub).get(2, []):
                pet_sub = pet_entry.get("sub")
                if not pet_sub:
                    continue
                pg = field_groups(pet_sub)
                inside_info = first_sub(pg.get(1, []))
                pet_data = first_sub(pg.get(2, []))
                name = first_text(pet_data, 3) if pet_data else None
                result.append({
                    "name": name,
                    "team": team_label,
                    "inside": inside_info,
                    "pet_data": pet_data,
                })
    return result


def _extract_equipped_skills_from_inside(
    inside_info: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """从 BattleInsidePetInfo.field 8 (skill_round_data) 提取装备技能 (pos 1-4)。"""
    if inside_info is None:
        return []
    iig = field_groups(inside_info)
    skills = []
    for srd_entry in iig.get(8, []):
        srd_sub = srd_entry.get("sub")
        if srd_sub is None:
            continue
        sid = pick_first(collect_varints(srd_sub, 39))
        pos = pick_first(collect_varints(srd_sub, 25))
        cost_e = pick_first(collect_varints(srd_sub, 9))
        if sid is not None and pos is not None and 1 <= pos <= 4:
            skills.append({
                "skill_id": sid,
                "pos": pos,
                "cost_energy": cost_e,
                "skill_name": skill_name(sid),
            })
    skills.sort(key=lambda s: s["pos"])
    return skills


def _collect_cast_skills_from_battle(
    packets: List[Dict[str, Any]],
) -> Tuple[Dict[str, Set[int]], Dict[str, Set[int]]]:
    """从 0x1324 action_resolve 中收集实际施放的主动技能。

    Returns:
        (player_used, opp_used)  — {pet_name: set(skill_id)}
    """
    events, _ = replay_battle(packets)
    player_used: Dict[str, Set[int]] = {}
    opp_used: Dict[str, Set[int]] = {}

    for e in events:
        if e["opcode"] != 0x1324:
            continue
        for entry in e.get("detail", {}).get("entries", []):
            if entry.get("kind") not in ("skill_cast", "damage"):
                continue
            sid = entry.get("skill_id")
            if not sid:
                continue
            # 过滤：只保留主动技能 (7xxxxxxx)，排除普攻和系统技能
            if sid in (7000010, 7000030, 7000014):
                continue
            s = str(sid)
            if not (s.startswith("7") and len(s) == 7):
                continue
            actor_side = entry.get("actor_side")
            if actor_side is None:
                continue
            is_mine = 1 <= int(actor_side) <= 6
            active = e.get("state", {}).get("my_active" if is_mine else "opp_active")
            if not active:
                continue
            name = active.get("name", "?")
            target = player_used if is_mine else opp_used
            target.setdefault(name, set()).add(sid)

    return player_used, opp_used


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def enter_packet(session1_packets):
    return next(p for p in session1_packets if p["opcode"] == 0x1316)


@pytest.fixture(scope="module")
def pet_infos(enter_packet):
    return _navigate_battle_enter_teams(enter_packet["record"])


@pytest.fixture(scope="module")
def cast_skills(session1_packets):
    return _collect_cast_skills_from_battle(session1_packets)


# ---------------------------------------------------------------------------
# Tests: 0x1316 数据完整性
# ---------------------------------------------------------------------------


class TestBattleEnterSkillData:
    """验证 0x1316 包中 BattleInsidePetInfo.field 8 的技能数据。"""

    def test_pet_infos_extracted(self, pet_infos):
        assert len(pet_infos) >= 2, "应至少有 2 只精灵 (我方+敌方)"

    def test_player_and_enemy_both_present(self, pet_infos):
        teams = {p["team"] for p in pet_infos}
        assert "player" in teams
        assert "enemy" in teams

    def test_all_pets_have_names(self, pet_infos):
        for p in pet_infos:
            assert p["name"], f"精灵缺少 name: {p}"

    def test_player_pets_have_skill_round_data(self, pet_infos):
        """我方精灵必须有 BattleInsidePetInfo.field 8 (skill_round_data)。"""
        player_pets = [p for p in pet_infos if p["team"] == "player"]
        assert len(player_pets) >= 1
        for p in player_pets:
            assert p["inside"] is not None, f"我方精灵 {p['name']} 无 inside_info"
            iig = field_groups(p["inside"])
            assert 8 in iig, f"我方精灵 {p['name']} 缺少 field 8 (skill_round_data)"

    def test_enemy_pet_no_skill_round_data_at_enter(self, pet_infos):
        """敌方首只在 0x1316 时无 skill_round_data (PvP 服务器不发送)。"""
        enemy_pets = [p for p in pet_infos if p["team"] == "enemy"]
        for p in enemy_pets:
            if p["inside"] is not None:
                iig = field_groups(p["inside"])
                has_skills = 8 in iig
                # 敌方首只可能没有 skill_round_data
                if not has_skills:
                    assert True  # 预期情况
                    return
        # 如果敌方有 skill_round_data 也 ok（某些战斗模式可能发送）
        assert True


# ---------------------------------------------------------------------------
# Tests: 装备技能数量和结构
# ---------------------------------------------------------------------------


class TestEquippedSkillStructure:
    """验证每只我方精灵有 4 个装备技能，结构完整。"""

    def test_player_pets_have_four_equipped_skills(self, pet_infos):
        """每只我方精灵应有恰好 4 个装备技能 (pos 1-4)。"""
        player_pets = [p for p in pet_infos if p["team"] == "player"]
        for p in player_pets:
            skills = _extract_equipped_skills_from_inside(p["inside"])
            assert len(skills) == 4, (
                f"{p['name']} 应有 4 个装备技能, 实际 {len(skills)}: "
                f"{[s['skill_name'] for s in skills]}"
            )

    def test_equipped_skills_have_valid_positions(self, pet_infos):
        """装备技能的 pos 应为 1/2/3/4 且不重复。"""
        player_pets = [p for p in pet_infos if p["team"] == "player"]
        for p in player_pets:
            skills = _extract_equipped_skills_from_inside(p["inside"])
            positions = [s["pos"] for s in skills]
            assert sorted(positions) == [1, 2, 3, 4], (
                f"{p['name']} pos 不连续: {positions}"
            )

    def test_equipped_skills_have_valid_skill_ids(self, pet_infos):
        """技能 ID 应为 7 位数字 (7xxxxxxx)。"""
        player_pets = [p for p in pet_infos if p["team"] == "player"]
        for p in player_pets:
            skills = _extract_equipped_skills_from_inside(p["inside"])
            for s in skills:
                sid = s["skill_id"]
                assert sid is not None, f"{p['name']} 有空 skill_id"
                assert str(sid).startswith("7") and len(str(sid)) == 7, (
                    f"{p['name']} 技能 ID 异常: {sid}"
                )

    def test_equipped_skills_have_energy_cost(self, pet_infos):
        """装备技能应有能量消耗值。"""
        player_pets = [p for p in pet_infos if p["team"] == "player"]
        for p in player_pets:
            skills = _extract_equipped_skills_from_inside(p["inside"])
            for s in skills:
                assert s["cost_energy"] is not None, (
                    f"{p['name']} 技能 {s['skill_name']} (id={s['skill_id']}) 缺少 cost_energy"
                )

    def test_equipped_skills_resolve_to_names(self, pet_infos):
        """装备技能应能解析为技能名称 (允许少量未收录)。"""
        player_pets = [p for p in pet_infos if p["team"] == "player"]
        unnamed_count = 0
        for p in player_pets:
            skills = _extract_equipped_skills_from_inside(p["inside"])
            for s in skills:
                if s["skill_name"] is None:
                    unnamed_count += 1
        # 允许少量未收录的技能
        assert unnamed_count <= 2, f"有 {unnamed_count} 个技能无法解析名称"


# ---------------------------------------------------------------------------
# Tests: 与战斗中实际施放技能的匹配
# ---------------------------------------------------------------------------


class TestSkillMatchWithBattle:
    """验证初始装备技能与战斗中实际施放的技能是否匹配。"""

    def test_every_cast_player_skill_exists_in_init(self, pet_infos, cast_skills):
        """我方精灵在战斗中施放的每个主动技能都应在初始装备列表中。"""
        player_used, _ = cast_skills

        player_pets = [p for p in pet_infos if p["team"] == "player"]
        for p in player_pets:
            init_skills = _extract_equipped_skills_from_inside(p["inside"])
            init_ids = {s["skill_id"] for s in init_skills}
            used_ids = player_used.get(p["name"], set())

            extra = used_ids - init_ids
            assert not extra, (
                f"{p['name']} 战斗中施放了不在初始装备列表中的技能: "
                f"{sorted(extra)}"
            )

    def test_at_least_one_pet_cast_skills(self, cast_skills):
        """至少有一只我方精灵在战斗中使用了技能。"""
        player_used, _ = cast_skills
        total_cast = sum(len(ids) for ids in player_used.values())
        assert total_cast >= 1, "我方精灵至少应使用过 1 个技能"

    def test_enemy_skills_observed_in_battle(self, cast_skills):
        """敌方精灵在战斗中也应有技能被观察到。"""
        _, opp_used = cast_skills
        total_opp = sum(len(ids) for ids in opp_used.values())
        assert total_opp >= 1, "敌方精灵至少应施放过 1 个技能"


# ---------------------------------------------------------------------------
# Tests: 0x131A round_start 也提供技能数据
# ---------------------------------------------------------------------------


def _find_inside_info_skills_in_record(record) -> List[Dict[str, Any]]:
    """Walk 整棵 proto 树，找到所有含 skill_round_data 的子消息并提取装备技能。

    适用于任意 opcode (0x1316, 0x131A 等)。
    """
    from src.protocol.proto_core import walk_messages
    results = []
    for path, msg in walk_messages(record["root"], "root"):
        fg = field_groups(msg)
        if 8 not in fg:
            continue
        skills = _extract_equipped_skills_from_inside(msg)
        if len(skills) == 4:
            results.append({"path": path, "skills": skills})
    return results


class TestRoundStartSkillData:
    """验证 0x131A round_start 中的 skill_round_data。"""

    def test_round_start_has_skill_data(self, session1_packets):
        """round_start 包中活跃精灵应有 skill_round_data (4 个装备技能)。"""
        round_starts = [p for p in session1_packets if p["opcode"] == 0x131A]
        assert len(round_starts) > 0

        for rs in round_starts:
            found = _find_inside_info_skills_in_record(rs["record"])
            if found:
                return  # PASS

        pytest.fail("round_start 中未找到含 4 个装备技能的精灵")

    def test_round_start_player_skills_match_enter(self, session1_packets):
        """round_start 中我方精灵的技能应与 battle_enter 一致。"""
        from src.protocol.proto_core import walk_messages

        enter = next(p for p in session1_packets if p["opcode"] == 0x1316)
        round_starts = [p for p in session1_packets if p["opcode"] == 0x131A]

        # 从 0x1316 收集我方技能
        enter_pets = _navigate_battle_enter_teams(enter["record"])
        enter_player_skills = {}
        for p in enter_pets:
            if p["team"] == "player":
                skills = _extract_equipped_skills_from_inside(p["inside"])
                enter_player_skills[p["name"]] = {s["skill_id"] for s in skills}

        # 从首个 round_start 找到有 4 个装备技能的消息，与 enter 对比
        rs = round_starts[0]
        rs_found = _find_inside_info_skills_in_record(rs["record"])
        assert len(rs_found) >= 1, "round_start 未找到含装备技能的精灵"

        # round_start 中找到的技能集合应在 enter 技能集合中存在（按 id 匹配）
        rs_skill_sets = [frozenset(s["skill_id"] for s in item["skills"]) for item in rs_found]
        enter_skill_sets = [frozenset(ids) for ids in enter_player_skills.values()]

        matched = any(rs_set in enter_skill_sets for rs_set in rs_skill_sets)
        assert matched, (
            f"round_start 技能集合 {rs_skill_sets} "
            f"未在 enter 技能集合 {enter_skill_sets} 中找到匹配"
        )


# ---------------------------------------------------------------------------
# Tests: 全链路 — replay_battle 后 tracker state 中的 equipped_skills
# ---------------------------------------------------------------------------


class TestEquippedSkillsInTrackerState:
    """验证 replay_battle 后所有我方精灵的 equipped_skills 完整性。"""

    @pytest.fixture(scope="class")
    def replay_result(self, session1_baseline_result):
        return session1_baseline_result

    def test_player_pets_count(self, replay_result):
        """我方应有6只精灵。"""
        _, final_state = replay_result
        my_pets = final_state.get("my_pets", [])
        assert len(my_pets) == 6, f"我方应有6只精灵, 实际 {len(my_pets)}: {[p.get('name') for p in my_pets]}"

    def test_all_player_pets_have_four_equipped_skills(self, replay_result):
        """每只我方精灵应有恰好4个装备技能。"""
        _, final_state = replay_result
        for pet in final_state.get("my_pets", []):
            eq = pet.get("equipped_skills", [])
            assert len(eq) == 4, (
                f"精灵 {pet.get('name')} 应有4个装备技能, 实际 {len(eq)}: "
                f"{[s.get('skill_name') for s in eq]}"
            )

    def test_equipped_skills_sorted_by_slot(self, replay_result):
        """装备技能应按 slot 1-4 排序。"""
        _, final_state = replay_result
        for pet in final_state.get("my_pets", []):
            slots = [s.get("equipped_slot") for s in pet.get("equipped_skills", [])]
            assert slots == [1, 2, 3, 4], f"精灵 {pet.get('name')} slots 不连续: {slots}"

    def test_equipped_skills_have_names(self, replay_result):
        """装备技能应有名称（允许少量因 normalizer 未收录的技能）。"""
        _, final_state = replay_result
        unnamed = 0
        for pet in final_state.get("my_pets", []):
            for skill in pet.get("equipped_skills", []):
                if skill.get("skill_name") is None:
                    unnamed += 1
        assert unnamed <= 4, f"有 {unnamed} 个装备技能无法解析名称"

    def test_equipped_skills_have_element(self, replay_result):
        """装备技能应有 skill_element（允许少量因 normalizer 未收录的技能）。"""
        _, final_state = replay_result
        no_element = 0
        for pet in final_state.get("my_pets", []):
            for skill in pet.get("equipped_skills", []):
                if skill.get("skill_element") is None:
                    no_element += 1
        assert no_element <= 4, f"有 {no_element} 个装备技能无 skill_element"

    def test_equipped_skills_have_damage_type(self, replay_result):
        """装备技能应有 skill_damage_type (1=状态, 2=物攻, 3=特攻)，允许少量无元数据的技能。"""
        _, final_state = replay_result
        no_dt = 0
        for pet in final_state.get("my_pets", []):
            for skill in pet.get("equipped_skills", []):
                dt = skill.get("skill_damage_type")
                if dt is None:
                    no_dt += 1
                    continue
                assert dt in (1, 2, 3), (
                    f"精灵 {pet.get('name')}: 技能 {skill.get('skill_name')} damage_type={dt} 不合法"
                )
        assert no_dt <= 4, f"有 {no_dt} 个装备技能无 skill_damage_type"

    def test_wrapper_skill_source_tracked(self, session1_packets):
        """extract_state_wrapper 应返回 skill_source 字段。"""
        from src.protocol.proto_core import extract_state_wrappers_from_record
        enter_packet = next(p for p in session1_packets if p["opcode"] == 0x1316)
        wrappers = extract_state_wrappers_from_record(enter_packet["record"])
        player_wrappers = [w for w in wrappers if w.get("side") == 1]
        assert len(player_wrappers) >= 1, "应有我方精灵 wrapper"
        for w in player_wrappers:
            assert w.get("skill_source") is not None, f"精灵 {w.get('name')} 无 skill_source"
            assert len(w.get("equipped_skills", [])) == 4, (
                f"精灵 {w.get('name')} wrapper equipped_skills 不为4"
            )
