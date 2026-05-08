"""Tests for SkillDamType → elemental type ID mapping."""
import pytest
from src.protocol.proto_core import SDT_TO_TYPE, extract_creature


class TestSDTMapping:
    """Verify SkillDamType enum values map to correct type IDs."""

    def test_water(self):
        assert SDT_TO_TYPE[5] == 2  # SDT_WATER → 水

    def test_poison(self):
        assert SDT_TO_TYPE[12] == 7  # SDT_TOXIC → 毒

    def test_fire(self):
        assert SDT_TO_TYPE[4] == 1  # SDT_FIRE → 火

    def test_grass_same_value(self):
        assert SDT_TO_TYPE[3] == 3  # SDT_GRASS → 草 (coincidental match)

    def test_ice(self):
        assert SDT_TO_TYPE[9] == 5  # SDT_ICE → 冰

    def test_electric(self):
        assert SDT_TO_TYPE[11] == 4  # SDT_ELECTRIC → 电

    def test_dragon(self):
        assert SDT_TO_TYPE[10] == 15  # SDT_DRAGON → 龙

    def test_fighting(self):
        assert SDT_TO_TYPE[14] == 6  # SDT_FIGHT → 武

    def test_flying(self):
        assert SDT_TO_TYPE[15] == 9  # SDT_WING → 翼

    def test_cute(self):
        assert SDT_TO_TYPE[16] == 10  # SDT_MOE → 萌

    def test_psychic(self):
        assert SDT_TO_TYPE[20] == 11  # SDT_PHANTOM → 幻

    def test_bug(self):
        assert SDT_TO_TYPE[13] == 12  # SDT_INSECT → 虫

    def test_ghost(self):
        assert SDT_TO_TYPE[17] == 13  # SDT_GHOST → 幽

    def test_mechanical(self):
        assert SDT_TO_TYPE[19] == 14  # SDT_MECHANIC → 机械

    def test_dark(self):
        assert SDT_TO_TYPE[18] == 16  # SDT_DEMON → 恶

    def test_light(self):
        assert SDT_TO_TYPE[6] == 17  # SDT_LIGHT → 光

    def test_ground(self):
        assert SDT_TO_TYPE[7] == 8  # SDT_EARTH → 地

    def test_normal_common(self):
        assert SDT_TO_TYPE[2] == 0  # SDT_COMMON → 普通

    def test_normal_general(self):
        assert SDT_TO_TYPE[23] == 0  # SDT_GENERAL → 普通

    def test_all_types_covered(self):
        expected_types = set(range(18))  # types 0-17
        mapped_types = set(SDT_TO_TYPE.values())
        assert expected_types == mapped_types


class TestCreatureTypeExtraction:
    """Verify extract_creature applies SDT_TO_TYPE mapping."""

    @staticmethod
    def _make_msg(types_sdt, name="测试精灵", level=50, pet_id=1001):
        fields = []
        fields.append({"field": 1, "wire": 0, "offset": 0, "value": 1})  # slot
        fields.append({"field": 2, "wire": 0, "offset": 0, "value": pet_id})
        fields.append({"field": 3, "wire": 2, "offset": 0, "text": name, "raw_hex": name.encode().hex()})
        for sdt in types_sdt:
            fields.append({"field": 6, "wire": 0, "offset": 0, "value": sdt})
        fields.append({"field": 10, "wire": 0, "offset": 0, "value": level})
        return {"fields": fields, "consumed": 100, "clean": True}

    def test_qianji_kuai(self):
        """千棘盔: SDT values [5,12] should map to type IDs [2,7]."""
        msg = self._make_msg([5, 12], name="千棘盔", pet_id=14000428)
        record = {"opcode": 0x1316, "opcode_hex": "0x1316", "seq": 1}
        creature = extract_creature(msg, path="root.test", record=record)
        assert creature is not None
        assert creature["types"] == [2, 7]

    def test_fire_pet(self):
        """Fire pet: SDT_FIRE(4) → type 1."""
        msg = self._make_msg([4])
        record = {"opcode": 0x1316, "opcode_hex": "0x1316", "seq": 1}
        creature = extract_creature(msg, path="root.test", record=record)
        assert creature is not None
        assert creature["types"] == [1]

    def test_dual_type_pet(self):
        """Dual type: SDT_FIRE(4) + SDT_ICE(9) → types [1, 5]."""
        msg = self._make_msg([4, 9])
        record = {"opcode": 0x1316, "opcode_hex": "0x1316", "seq": 1}
        creature = extract_creature(msg, path="root.test", record=record)
        assert creature is not None
        assert creature["types"] == [1, 5]

    def test_grass_passthrough(self):
        """Grass type: SDT_GRASS(3) = type 3 (same value, should still work)."""
        msg = self._make_msg([3])
        record = {"opcode": 0x1316, "opcode_hex": "0x1316", "seq": 1}
        creature = extract_creature(msg, path="root.test", record=record)
        assert creature is not None
        assert creature["types"] == [3]

    def test_unknown_sdt_passthrough(self):
        """Unknown SDT values should pass through unchanged."""
        msg = self._make_msg([99])
        record = {"opcode": 0x1316, "opcode_hex": "0x1316", "seq": 1}
        creature = extract_creature(msg, path="root.test", record=record)
        assert creature is not None
        assert creature["types"] == [99]

    def test_no_types(self):
        """Pet with no type fields should have empty types list."""
        msg = self._make_msg([], name="无属性", pet_id=1002)
        record = {"opcode": 0x1316, "opcode_hex": "0x1316", "seq": 1}
        creature = extract_creature(msg, path="root.test", record=record)
        assert creature is not None
        assert creature["types"] == []
