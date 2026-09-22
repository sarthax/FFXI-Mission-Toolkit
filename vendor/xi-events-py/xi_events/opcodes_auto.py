"""Auto-generated. Re-run scripts/generate_opcodes.py to refresh."""

from __future__ import annotations

from luaparser import astnodes as N

from . import work_area as W
from .custom_parsers import PARSERS as _CUSTOM_PARSERS
from .registry import op

_ASCII_HINT_NAMES = ("scheduler_id", "action_id", "animation", "ext_scheduler_id")
_SENTINEL_LO, _SENTINEL_HI = 0x7FFFFFC0, 0x7FFFFFFF
_ENTITY_LO, _ENTITY_HI = 0x01000000, 0x01FFFFFF

# u16 operand names that hold a *work-area address* (and should be rendered as
# ``scratch[N] / params[N] / state[N] / imed[N]`` etc). Anything not in this
# allow-list, and not suffixed with ``_offset``, is treated as a scalar literal
# — by far the more common case (server ids, durations, modes, coords, ...).
_WORK_ADDR_NAMES = frozenset(
    [
        "dest_value",
        "source_value",
        "val1",
        "val2",
        "input",
        "result",
        "source",
        "dest",
        "default_option",
        "x_input",
        "y_input",
    ]
)
_BRANCH_OPERAND_NAMES = frozenset(
    [
        "target",
        "else_target",
        "else_offset",
        "jump_offset",
        "offset",
        "first_offset",
        "second_offset",
    ]
)


def _is_work_addr_u16(name):
    if name in _BRANCH_OPERAND_NAMES:
        return False
    if name in _WORK_ADDR_NAMES:
        return True
    return name.endswith("_offset") or name.endswith("_destination")


def _generic_emit(opname, operands=()):
    """Render an opcode invocation as ``vm:camelName(arg1, arg2, ...)``.

    Operand types from the catalog drive how each value is rendered:
    - ``u8`` → literal number (u8 fields can never be a work-area address).
    - ``u32`` → resolved as an entity name when in the sentinel or real-id
      ranges, an ASCII action id when shaped like one, else as a work value.
    - ``u16`` and unspecified → resolved as a work-area reference; ASCII-shaped
      values get rendered as quoted action ids.

    Variable-length opcodes go through ``custom_parse`` and bypass the operand
    list — their args appear in ``vars(a)`` and we fall back to the heuristic.
    """

    op_types = {name: type_ for name, type_ in operands}

    def emit(ctx, a):
        args = []
        for k, v in vars(a).items():
            if k == "raw":
                if isinstance(v, (bytes, bytearray)):
                    args.append(W.lua_string(v.hex()))
                continue
            type_ = op_types.get(k)
            if isinstance(v, int):
                args.append(_render_int(ctx, k, v, type_))
            elif isinstance(v, (bytes, bytearray)):
                args.append(W.lua_string(v.hex()))
            else:
                args.append(N.Name(str(v)))
        return ctx.invoke("vm", _camel(opname), args)

    return emit


def _render_int(ctx, name, value, type_):
    if type_ == "u8":
        return N.Number(value)
    if type_ == "u32":
        if _SENTINEL_LO <= value <= _SENTINEL_HI or _ENTITY_LO <= value <= _ENTITY_HI:
            return ctx.entity(value)
        if name in _ASCII_HINT_NAMES or _looks_ascii(value):
            return W.lua_string(W.action_id(value))
        return ctx.value(value)
    # u16 (and untyped fallback for custom-parsed opcodes).
    if _SENTINEL_LO <= value <= _SENTINEL_HI:
        return ctx.entity(value)
    if _ENTITY_LO <= value <= _ENTITY_HI:
        return ctx.entity(value)
    if name in _ASCII_HINT_NAMES or _looks_ascii(value):
        return W.lua_string(W.action_id(value))
    # IMED reference (the VM resolves these regardless of operand role).
    if 0x8000 <= value <= 0x8FFF:
        return ctx.value(value)
    if type_ == "u16" and not _is_work_addr_u16(name):
        return N.Number(value)
    return ctx.value(value)


def _camel(name):
    parts = name.lower().split("_")
    return parts[0] + "".join(p.title() for p in parts[1:])


def _looks_ascii(v):
    if not (0x20202020 <= v <= 0x7E7E7E7E):
        return False
    bs = (v & 0xFF, (v >> 8) & 0xFF, (v >> 16) & 0xFF, (v >> 24) & 0xFF)
    return all(0x20 <= b <= 0x7E for b in bs)


@op(0x00, "END_REQSTACK", terminal=True)
def _auto_00(ctx, a):
    return _generic_emit("END_REQSTACK")(ctx, a)


@op(
    0x01,
    "GOTO",
    operands=[("offset", "u16")],
    terminal=True,
    branches=lambda a: [a.offset],
)
def _auto_01(ctx, a):
    return _generic_emit("GOTO", (("offset", "u16"),))(ctx, a)


@op(
    0x02,
    "IF_CONDITIONAL",
    operands=[
        ("val1", "u16"),
        ("val2", "u16"),
        ("condition_type", "u8"),
        ("else_offset", "u16"),
    ],
    branches=lambda a: [a.else_offset],
)
def _auto_02(ctx, a):
    return _generic_emit(
        "IF_CONDITIONAL",
        (
            ("val1", "u16"),
            ("val2", "u16"),
            ("condition_type", "u8"),
            ("else_offset", "u16"),
        ),
    )(ctx, a)


@op(
    0x03, "COPY_WORK_VALUE", operands=[("dest_offset", "u16"), ("source_offset", "u16")]
)
def _auto_03(ctx, a):
    return _generic_emit(
        "COPY_WORK_VALUE",
        (
            ("dest_offset", "u16"),
            ("source_offset", "u16"),
        ),
    )(ctx, a)


@op(0x04, "DEPRECATED_NOP", operands=[("unused", "u16")])
def _auto_04(ctx, a):
    return _generic_emit("DEPRECATED_NOP", (("unused", "u16"),))(ctx, a)


@op(0x05, "SET_ONE", operands=[("target", "u16")])
def _auto_05(ctx, a):
    return _generic_emit("SET_ONE", (("target", "u16"),))(ctx, a)


@op(0x06, "SET_ZERO", operands=[("target", "u16")])
def _auto_06(ctx, a):
    return _generic_emit("SET_ZERO", (("target", "u16"),))(ctx, a)


@op(0x07, "ADD_VALUES", operands=[("dest_value", "u16"), ("source_value", "u16")])
def _auto_07(ctx, a):
    return _generic_emit(
        "ADD_VALUES",
        (
            ("dest_value", "u16"),
            ("source_value", "u16"),
        ),
    )(ctx, a)


@op(0x08, "SUBTRACT_VALUES", operands=[("dest_value", "u16"), ("source_value", "u16")])
def _auto_08(ctx, a):
    return _generic_emit(
        "SUBTRACT_VALUES",
        (
            ("dest_value", "u16"),
            ("source_value", "u16"),
        ),
    )(ctx, a)


@op(0x09, "SET_BIT_FLAG", operands=[("target", "u16"), ("bit_position", "u16")])
def _auto_09(ctx, a):
    return _generic_emit(
        "SET_BIT_FLAG",
        (
            ("target", "u16"),
            ("bit_position", "u16"),
        ),
    )(ctx, a)


@op(0x0A, "CLEAR_BIT_FLAG", operands=[("target", "u16"), ("bit_position", "u16")])
def _auto_0A(ctx, a):
    return _generic_emit(
        "CLEAR_BIT_FLAG",
        (
            ("target", "u16"),
            ("bit_position", "u16"),
        ),
    )(ctx, a)


@op(0x0B, "INCREMENT_VALUE", operands=[("target", "u16")])
def _auto_0B(ctx, a):
    return _generic_emit("INCREMENT_VALUE", (("target", "u16"),))(ctx, a)


@op(0x0C, "DECREMENT_VALUE", operands=[("target", "u16")])
def _auto_0C(ctx, a):
    return _generic_emit("DECREMENT_VALUE", (("target", "u16"),))(ctx, a)


@op(0x0D, "BITWISE_AND", operands=[("dest_value", "u16"), ("source_value", "u16")])
def _auto_0D(ctx, a):
    return _generic_emit(
        "BITWISE_AND",
        (
            ("dest_value", "u16"),
            ("source_value", "u16"),
        ),
    )(ctx, a)


@op(0x0E, "BITWISE_OR", operands=[("dest_value", "u16"), ("source_value", "u16")])
def _auto_0E(ctx, a):
    return _generic_emit(
        "BITWISE_OR",
        (
            ("dest_value", "u16"),
            ("source_value", "u16"),
        ),
    )(ctx, a)


@op(0x0F, "BITWISE_XOR", operands=[("dest_value", "u16"), ("source_value", "u16")])
def _auto_0F(ctx, a):
    return _generic_emit(
        "BITWISE_XOR",
        (
            ("dest_value", "u16"),
            ("source_value", "u16"),
        ),
    )(ctx, a)


@op(
    0x10,
    "BITWISE_LEFT_SHIFT",
    operands=[("dest_value", "u16"), ("source_value", "u16")],
)
def _auto_10(ctx, a):
    return _generic_emit(
        "BITWISE_LEFT_SHIFT",
        (
            ("dest_value", "u16"),
            ("source_value", "u16"),
        ),
    )(ctx, a)


@op(
    0x11,
    "BITWISE_RIGHT_SHIFT",
    operands=[("dest_value", "u16"), ("source_value", "u16")],
)
def _auto_11(ctx, a):
    return _generic_emit(
        "BITWISE_RIGHT_SHIFT",
        (
            ("dest_value", "u16"),
            ("source_value", "u16"),
        ),
    )(ctx, a)


@op(0x12, "GENERATE_RANDOM", operands=[("target", "u16")])
def _auto_12(ctx, a):
    return _generic_emit("GENERATE_RANDOM", (("target", "u16"),))(ctx, a)


@op(0x13, "GENERATE_RANDOM_RANGE", operands=[("target", "u16"), ("max_value", "u16")])
def _auto_13(ctx, a):
    return _generic_emit(
        "GENERATE_RANDOM_RANGE",
        (
            ("target", "u16"),
            ("max_value", "u16"),
        ),
    )(ctx, a)


@op(0x14, "MULTIPLY_VALUES", operands=[("dest_value", "u16"), ("source_value", "u16")])
def _auto_14(ctx, a):
    return _generic_emit(
        "MULTIPLY_VALUES",
        (
            ("dest_value", "u16"),
            ("source_value", "u16"),
        ),
    )(ctx, a)


@op(0x15, "DIVIDE_VALUES", operands=[("dest_value", "u16"), ("source_value", "u16")])
def _auto_15(ctx, a):
    return _generic_emit(
        "DIVIDE_VALUES",
        (
            ("dest_value", "u16"),
            ("source_value", "u16"),
        ),
    )(ctx, a)


@op(
    0x16,
    "SINE_CALCULATION",
    operands=[("result", "u16"), ("input", "u16"), ("multiplier", "u16")],
)
def _auto_16(ctx, a):
    return _generic_emit(
        "SINE_CALCULATION",
        (
            ("result", "u16"),
            ("input", "u16"),
            ("multiplier", "u16"),
        ),
    )(ctx, a)


@op(
    0x17,
    "COSINE_CALCULATION",
    operands=[("result", "u16"), ("input", "u16"), ("multiplier", "u16")],
)
def _auto_17(ctx, a):
    return _generic_emit(
        "COSINE_CALCULATION",
        (
            ("result", "u16"),
            ("input", "u16"),
            ("multiplier", "u16"),
        ),
    )(ctx, a)


@op(
    0x18,
    "ATAN2_CALCULATION",
    operands=[("result", "u16"), ("y_input", "u16"), ("x_input", "u16")],
)
def _auto_18(ctx, a):
    return _generic_emit(
        "ATAN2_CALCULATION",
        (
            ("result", "u16"),
            ("y_input", "u16"),
            ("x_input", "u16"),
        ),
    )(ctx, a)


@op(0x19, "SWAP_VALUES", operands=[("first_offset", "u16"), ("second_offset", "u16")])
def _auto_19(ctx, a):
    return _generic_emit(
        "SWAP_VALUES",
        (
            ("first_offset", "u16"),
            ("second_offset", "u16"),
        ),
    )(ctx, a)


@op(
    0x1A,
    "JUMP_TO_POSITION",
    operands=[("offset", "u16")],
    branches=lambda a: [a.offset],
)
def _auto_1A(ctx, a):
    return _generic_emit("JUMP_TO_POSITION", (("offset", "u16"),))(ctx, a)


@op(0x1B, "RETURN_FROM_JUMP", terminal=True)
def _auto_1B(ctx, a):
    return _generic_emit("RETURN_FROM_JUMP")(ctx, a)


@op(0x1C, "WAIT_TIME", operands=[("wait_value", "u16")])
def _auto_1C(ctx, a):
    return _generic_emit("WAIT_TIME", (("wait_value", "u16"),))(ctx, a)


@op(0x1D, "PRINT_EVENT_MESSAGE", operands=[("message_id", "u16")])
def _auto_1D(ctx, a):
    return _generic_emit("PRINT_EVENT_MESSAGE", (("message_id", "u16"),))(ctx, a)


@op(0x1E, "ENTITY_LOOK_AT_AND_TALK", operands=[("target_entity", "u32")])
def _auto_1E(ctx, a):
    return _generic_emit("ENTITY_LOOK_AT_AND_TALK", (("target_entity", "u32"),))(ctx, a)


@op(0x1F, "MOVE_ENTITY", custom_parse=_CUSTOM_PARSERS[0x1F])
def _auto_1F(ctx, a):
    return _generic_emit("MOVE_ENTITY")(ctx, a)


@op(0x20, "SET_CLI_EVENT_UC_FLAG", operands=[("flag_value", "u8")])
def _auto_20(ctx, a):
    return _generic_emit("SET_CLI_EVENT_UC_FLAG", (("flag_value", "u8"),))(ctx, a)


@op(0x21, "END_EVENT", terminal=True)
def _auto_21(ctx, a):
    return _generic_emit("END_EVENT")(ctx, a)


@op(0x22, "ENTITY_HIDE_FLAG", operands=[("enabled", "u8")])
def _auto_22(ctx, a):
    return _generic_emit("ENTITY_HIDE_FLAG", (("enabled", "u8"),))(ctx, a)


@op(0x23, "WAIT_FOR_DIALOG_INTERACTION")
def _auto_23(ctx, a):
    return _generic_emit("WAIT_FOR_DIALOG_INTERACTION")(ctx, a)


@op(
    0x24,
    "CREATE_DIALOG",
    operands=[
        ("message_id", "u16"),
        ("default_option", "u16"),
        ("option_flags", "u16"),
    ],
)
def _auto_24(ctx, a):
    return _generic_emit(
        "CREATE_DIALOG",
        (
            ("message_id", "u16"),
            ("default_option", "u16"),
            ("option_flags", "u16"),
        ),
    )(ctx, a)


@op(0x25, "WAIT_DIALOG_SELECT")
def _auto_25(ctx, a):
    return _generic_emit("WAIT_DIALOG_SELECT")(ctx, a)


@op(0x26, "YIELD_VM", terminal=True)
def _auto_26(ctx, a):
    return _generic_emit("YIELD_VM")(ctx, a)


@op(
    0x27,
    "REQ_SET",
    operands=[("priority", "u8"), ("entity_id", "u32"), ("tag_num", "u8")],
)
def _auto_27(ctx, a):
    return _generic_emit(
        "REQ_SET",
        (
            ("priority", "u8"),
            ("entity_id", "u32"),
            ("tag_num", "u8"),
        ),
    )(ctx, a)


@op(
    0x28,
    "REQ_SET_WITH_CONDITIONS",
    operands=[("priority", "u8"), ("entity_id", "u32"), ("tag_num", "u8")],
)
def _auto_28(ctx, a):
    return _generic_emit(
        "REQ_SET_WITH_CONDITIONS",
        (
            ("priority", "u8"),
            ("entity_id", "u32"),
            ("tag_num", "u8"),
        ),
    )(ctx, a)


@op(
    0x29,
    "REQ_SET_WAIT",
    operands=[
        ("priority", "u8"),
        ("server_id1", "u16"),
        ("server_id2", "u16"),
        ("tag_num", "u8"),
    ],
)
def _auto_29(ctx, a):
    return _generic_emit(
        "REQ_SET_WAIT",
        (
            ("priority", "u8"),
            ("server_id1", "u16"),
            ("server_id2", "u16"),
            ("tag_num", "u8"),
        ),
    )(ctx, a)


@op(0x2A, "GET_REQ_LEVEL", operands=[("level", "u8"), ("entity_id", "u32")])
def _auto_2A(ctx, a):
    return _generic_emit(
        "GET_REQ_LEVEL",
        (
            ("level", "u8"),
            ("entity_id", "u32"),
        ),
    )(ctx, a)


@op(0x2B, "PRINT_ENTITY_MESSAGE", operands=[("entity_id", "u32"), ("message", "u16")])
def _auto_2B(ctx, a):
    return _generic_emit(
        "PRINT_ENTITY_MESSAGE",
        (
            ("entity_id", "u32"),
            ("message", "u16"),
        ),
    )(ctx, a)


@op(
    0x2C,
    "CREATE_SCHEDULER_TASK",
    operands=[("entity1_id", "u32"), ("entity2_id", "u32"), ("scheduler_id", "u32")],
)
def _auto_2C(ctx, a):
    return _generic_emit(
        "CREATE_SCHEDULER_TASK",
        (
            ("entity1_id", "u32"),
            ("entity2_id", "u32"),
            ("scheduler_id", "u32"),
        ),
    )(ctx, a)


@op(
    0x2D,
    "CREATE_ZONE_SCHEDULER_TASK",
    operands=[("entity1", "u32"), ("entity2", "u32"), ("zone_action", "u32")],
)
def _auto_2D(ctx, a):
    return _generic_emit(
        "CREATE_ZONE_SCHEDULER_TASK",
        (
            ("entity1", "u32"),
            ("entity2", "u32"),
            ("zone_action", "u32"),
        ),
    )(ctx, a)


@op(0x2E, "SET_CLI_EVENT_CANCEL_FLAGS")
def _auto_2E(ctx, a):
    return _generic_emit("SET_CLI_EVENT_CANCEL_FLAGS")(ctx, a)


@op(0x2F, "ADJUST_RENDER_FLAGS0", operands=[("flag", "u8"), ("entity_id", "u32")])
def _auto_2F(ctx, a):
    return _generic_emit(
        "ADJUST_RENDER_FLAGS0",
        (
            ("flag", "u8"),
            ("entity_id", "u32"),
        ),
    )(ctx, a)


@op(0x30, "SET_UCOFF_CONTINUE_ZERO")
def _auto_30(ctx, a):
    return _generic_emit("SET_UCOFF_CONTINUE_ZERO")(ctx, a)


@op(0x31, "UPDATE_ENTITY_POSITION", custom_parse=_CUSTOM_PARSERS[0x31])
def _auto_31(ctx, a):
    return _generic_emit("UPDATE_ENTITY_POSITION")(ctx, a)


@op(0x32, "SET_MAIN_SPEED", operands=[("speed", "u16")])
def _auto_32(ctx, a):
    return _generic_emit("SET_MAIN_SPEED", (("speed", "u16"),))(ctx, a)


@op(0x33, "ADJUST_EVENT_RENDER_FLAGS0", operands=[("flag", "u8")])
def _auto_33(ctx, a):
    return _generic_emit("ADJUST_EVENT_RENDER_FLAGS0", (("flag", "u8"),))(ctx, a)


@op(0x34, "LOAD_UNLOAD_ZONE", operands=[("zone_id", "u16")])
def _auto_34(ctx, a):
    return _generic_emit("LOAD_UNLOAD_ZONE", (("zone_id", "u16"),))(ctx, a)


@op(0x35, "LOAD_ZONE_NO_CLOSE", operands=[("zone_id", "u16")])
def _auto_35(ctx, a):
    return _generic_emit("LOAD_ZONE_NO_CLOSE", (("zone_id", "u16"),))(ctx, a)


@op(
    0x36,
    "SET_ENTITY_EVENT_POSITION",
    operands=[("x_position", "u16"), ("z_position", "u16"), ("y_position", "u16")],
)
def _auto_36(ctx, a):
    return _generic_emit(
        "SET_ENTITY_EVENT_POSITION",
        (
            ("x_position", "u16"),
            ("z_position", "u16"),
            ("y_position", "u16"),
        ),
    )(ctx, a)


@op(
    0x37,
    "UPDATE_EVENT_POSITION_AND_DIR",
    operands=[("x", "u16"), ("z", "u16"), ("y", "u16"), ("dir", "u16")],
)
def _auto_37(ctx, a):
    return _generic_emit(
        "UPDATE_EVENT_POSITION_AND_DIR",
        (
            ("x", "u16"),
            ("z", "u16"),
            ("y", "u16"),
            ("dir", "u16"),
        ),
    )(ctx, a)


@op(0x38, "SET_CLIENT_EVENT_MODE", operands=[("mode", "u16")])
def _auto_38(ctx, a):
    return _generic_emit("SET_CLIENT_EVENT_MODE", (("mode", "u16"),))(ctx, a)


@op(0x39, "SET_ENTITY_DIRECTION", operands=[("direction", "u16")])
def _auto_39(ctx, a):
    return _generic_emit("SET_ENTITY_DIRECTION", (("direction", "u16"),))(ctx, a)


@op(
    0x3A,
    "CONVERT_YAW_TO_BYTE",
    operands=[("entity_id", "u32"), ("result_destination", "u16")],
)
def _auto_3A(ctx, a):
    return _generic_emit(
        "CONVERT_YAW_TO_BYTE",
        (
            ("entity_id", "u32"),
            ("result_destination", "u16"),
        ),
    )(ctx, a)


@op(
    0x3B,
    "GET_ENTITY_POSITION",
    operands=[
        ("entity_id", "u32"),
        ("x_destination", "u16"),
        ("y_destination", "u16"),
        ("z_destination", "u16"),
    ],
)
def _auto_3B(ctx, a):
    return _generic_emit(
        "GET_ENTITY_POSITION",
        (
            ("entity_id", "u32"),
            ("x_destination", "u16"),
            ("y_destination", "u16"),
            ("z_destination", "u16"),
        ),
    )(ctx, a)


@op(
    0x3C,
    "SET_BIT_FLAG_CONDITIONAL",
    operands=[
        ("target_work_offset", "u16"),
        ("bit_index_work_offset", "u16"),
        ("condition_work_offset", "u16"),
    ],
)
def _auto_3C(ctx, a):
    return _generic_emit(
        "SET_BIT_FLAG_CONDITIONAL",
        (
            ("target_work_offset", "u16"),
            ("bit_index_work_offset", "u16"),
            ("condition_work_offset", "u16"),
        ),
    )(ctx, a)


@op(
    0x3D,
    "CLEAR_BIT_FLAG_CONDITIONAL",
    operands=[
        ("target_work_offset", "u16"),
        ("bit_index_work_offset", "u16"),
        ("condition_work_offset", "u16"),
    ],
)
def _auto_3D(ctx, a):
    return _generic_emit(
        "CLEAR_BIT_FLAG_CONDITIONAL",
        (
            ("target_work_offset", "u16"),
            ("bit_index_work_offset", "u16"),
            ("condition_work_offset", "u16"),
        ),
    )(ctx, a)


@op(
    0x3E,
    "TEST_BIT_AND_BRANCH",
    operands=[
        ("target_work_offset", "u16"),
        ("bit_index_work_offset", "u16"),
        ("jump_offset", "u16"),
    ],
    branches=lambda a: [a.jump_offset],
)
def _auto_3E(ctx, a):
    return _generic_emit(
        "TEST_BIT_AND_BRANCH",
        (
            ("target_work_offset", "u16"),
            ("bit_index_work_offset", "u16"),
            ("jump_offset", "u16"),
        ),
    )(ctx, a)


@op(
    0x3F,
    "MODULO_OPERATION",
    operands=[("target", "u16"), ("dividend", "u16"), ("divisor", "u16")],
)
def _auto_3F(ctx, a):
    return _generic_emit(
        "MODULO_OPERATION",
        (
            ("target", "u16"),
            ("dividend", "u16"),
            ("divisor", "u16"),
        ),
    )(ctx, a)


@op(
    0x40,
    "SET_BIT_WORK_RANGE",
    operands=[
        ("start_bit", "u16"),
        ("end_bit", "u16"),
        ("target", "u16"),
        ("source", "u16"),
    ],
)
def _auto_40(ctx, a):
    return _generic_emit(
        "SET_BIT_WORK_RANGE",
        (
            ("start_bit", "u16"),
            ("end_bit", "u16"),
            ("target", "u16"),
            ("source", "u16"),
        ),
    )(ctx, a)


@op(
    0x41,
    "GET_BIT_WORK_RANGE",
    operands=[
        ("start_bit", "u16"),
        ("end_bit", "u16"),
        ("source", "u16"),
        ("result", "u16"),
    ],
)
def _auto_41(ctx, a):
    return _generic_emit(
        "GET_BIT_WORK_RANGE",
        (
            ("start_bit", "u16"),
            ("end_bit", "u16"),
            ("source", "u16"),
            ("result", "u16"),
        ),
    )(ctx, a)


@op(0x42, "SET_CLI_EVENT_CANCEL_DATA")
def _auto_42(ctx, a):
    return _generic_emit("SET_CLI_EVENT_CANCEL_DATA")(ctx, a)


@op(0x43, "SEND_EVENT_UPDATE", operands=[("update_flag", "u8")])
def _auto_43(ctx, a):
    return _generic_emit("SEND_EVENT_UPDATE", (("update_flag", "u8"),))(ctx, a)


@op(
    0x44,
    "IF_ENTITY_VALID",
    operands=[("entity_id", "u16"), ("else_offset", "u16")],
    branches=lambda a: [a.else_offset],
)
def _auto_44(ctx, a):
    return _generic_emit(
        "IF_ENTITY_VALID",
        (
            ("entity_id", "u16"),
            ("else_offset", "u16"),
        ),
    )(ctx, a)


@op(
    0x45,
    "LOAD_SCHEDULED_TASK",
    operands=[
        ("first_work_offset", "u16"),
        ("entity1", "u32"),
        ("entity2", "u32"),
        ("scheduler_id", "u32"),
        ("second_work_offset", "u16"),
    ],
)
def _auto_45(ctx, a):
    return _generic_emit(
        "LOAD_SCHEDULED_TASK",
        (
            ("first_work_offset", "u16"),
            ("entity1", "u32"),
            ("entity2", "u32"),
            ("scheduler_id", "u32"),
            ("second_work_offset", "u16"),
        ),
    )(ctx, a)


@op(0x46, "CAMERA_CONTROL", operands=[("mode", "u8")])
def _auto_46(ctx, a):
    return _generic_emit("CAMERA_CONTROL", (("mode", "u8"),))(ctx, a)


@op(0x47, "UPDATE_PLAYER_LOCATION", custom_parse=_CUSTOM_PARSERS[0x47])
def _auto_47(ctx, a):
    return _generic_emit("UPDATE_PLAYER_LOCATION")(ctx, a)


@op(0x48, "PRINT_MESSAGE", operands=[("message_id", "u16")])
def _auto_48(ctx, a):
    return _generic_emit("PRINT_MESSAGE", (("message_id", "u16"),))(ctx, a)


@op(
    0x49,
    "PRINT_EVENT_MESSAGE_NO_SPEAKER",
    operands=[("target_entity", "u32"), ("message_id", "u16")],
)
def _auto_49(ctx, a):
    return _generic_emit(
        "PRINT_EVENT_MESSAGE_NO_SPEAKER",
        (
            ("target_entity", "u32"),
            ("message_id", "u16"),
        ),
    )(ctx, a)


@op(0x4A, "ENTITY_LOOK_AT", operands=[("entity1_id", "u32"), ("entity2_id", "u32")])
def _auto_4A(ctx, a):
    return _generic_emit(
        "ENTITY_LOOK_AT",
        (
            ("entity1_id", "u32"),
            ("entity2_id", "u32"),
        ),
    )(ctx, a)


@op(0x4B, "UPDATE_ENTITY_YAW", operands=[("entity", "u32"), ("yaw", "u16")])
def _auto_4B(ctx, a):
    return _generic_emit(
        "UPDATE_ENTITY_YAW",
        (
            ("entity", "u32"),
            ("yaw", "u16"),
        ),
    )(ctx, a)


@op(0x4C, "SET_ENTITY_STATUS_EVENT_DOOR")
def _auto_4C(ctx, a):
    return _generic_emit("SET_ENTITY_STATUS_EVENT_DOOR")(ctx, a)


@op(0x4D, "SET_ENTITY_STATUS_EVENT_CLOSE_DOOR")
def _auto_4D(ctx, a):
    return _generic_emit("SET_ENTITY_STATUS_EVENT_CLOSE_DOOR")(ctx, a)


@op(0x4E, "SET_ENTITY_HIDE_FLAG", operands=[("flag", "u8"), ("entity_id", "u32")])
def _auto_4E(ctx, a):
    return _generic_emit(
        "SET_ENTITY_HIDE_FLAG",
        (
            ("flag", "u8"),
            ("entity_id", "u32"),
        ),
    )(ctx, a)


@op(0x4F, "SET_ENTITY_STATUS_EVENT_CUSTOM", operands=[("status", "u16")])
def _auto_4F(ctx, a):
    return _generic_emit("SET_ENTITY_STATUS_EVENT_CUSTOM", (("status", "u16"),))(ctx, a)


@op(
    0x50,
    "END_SCHEDULER_TASK",
    operands=[
        ("first_entity", "u16"),
        ("first_param", "u16"),
        ("second_entity", "u16"),
        ("second_param", "u16"),
        ("action_id", "u16"),
        ("third_param", "u16"),
    ],
)
def _auto_50(ctx, a):
    return _generic_emit(
        "END_SCHEDULER_TASK",
        (
            ("first_entity", "u16"),
            ("first_param", "u16"),
            ("second_entity", "u16"),
            ("second_param", "u16"),
            ("action_id", "u16"),
            ("third_param", "u16"),
        ),
    )(ctx, a)


@op(
    0x51,
    "END_MAP_SCHEDULER",
    operands=[("entity1_id", "u32"), ("entity2_id", "u32"), ("scheduler_id", "u32")],
)
def _auto_51(ctx, a):
    return _generic_emit(
        "END_MAP_SCHEDULER",
        (
            ("entity1_id", "u32"),
            ("entity2_id", "u32"),
            ("scheduler_id", "u32"),
        ),
    )(ctx, a)


@op(
    0x52,
    "END_LOAD_SCHEDULER",
    operands=[
        ("work_offset", "u16"),
        ("entity1_id", "u32"),
        ("entity2_id", "u32"),
        ("scheduler_id", "u32"),
    ],
)
def _auto_52(ctx, a):
    return _generic_emit(
        "END_LOAD_SCHEDULER",
        (
            ("work_offset", "u16"),
            ("entity1_id", "u32"),
            ("entity2_id", "u32"),
            ("scheduler_id", "u32"),
        ),
    )(ctx, a)


@op(
    0x53,
    "WAIT_SCHEDULER_TASK",
    operands=[("entity1", "u32"), ("entity2", "u32"), ("action_id", "u32")],
)
def _auto_53(ctx, a):
    return _generic_emit(
        "WAIT_SCHEDULER_TASK",
        (
            ("entity1", "u32"),
            ("entity2", "u32"),
            ("action_id", "u32"),
        ),
    )(ctx, a)


@op(
    0x54,
    "WAIT_MAP_SCHEDULER",
    operands=[("entity1_id", "u32"), ("entity2_id", "u32"), ("action_id", "u32")],
)
def _auto_54(ctx, a):
    return _generic_emit(
        "WAIT_MAP_SCHEDULER",
        (
            ("entity1_id", "u32"),
            ("entity2_id", "u32"),
            ("action_id", "u32"),
        ),
    )(ctx, a)


@op(
    0x55,
    "WAIT_LOAD_SCHEDULER",
    operands=[
        ("scheduler_work_offset", "u16"),
        ("entity1", "u32"),
        ("entity2", "u32"),
        ("scheduler_id", "u32"),
    ],
)
def _auto_55(ctx, a):
    return _generic_emit(
        "WAIT_LOAD_SCHEDULER",
        (
            ("scheduler_work_offset", "u16"),
            ("entity1", "u32"),
            ("entity2", "u32"),
            ("scheduler_id", "u32"),
        ),
    )(ctx, a)


@op(
    0x56,
    "GET_ACTOR_INDEX_DEPRECATED",
    operands=[("entity", "u16"), ("unused_data", "u16")],
)
def _auto_56(ctx, a):
    return _generic_emit(
        "GET_ACTOR_INDEX_DEPRECATED",
        (
            ("entity", "u16"),
            ("unused_data", "u16"),
        ),
    )(ctx, a)


@op(0x57, "CREATE_FRAME_DELAY", operands=[("delay_work_offset", "u16")])
def _auto_57(ctx, a):
    return _generic_emit("CREATE_FRAME_DELAY", (("delay_work_offset", "u16"),))(ctx, a)


@op(0x58, "YIELD_EVENT_VM")
def _auto_58(ctx, a):
    return _generic_emit("YIELD_EVENT_VM")(ctx, a)


@op(0x59, "UPDATE_ENTITY_DATA_MULTI", custom_parse=_CUSTOM_PARSERS[0x59])
def _auto_59(ctx, a):
    return _generic_emit("UPDATE_ENTITY_DATA_MULTI")(ctx, a)


@op(0x5A, "UPDATE_EVENT_POSITION", custom_parse=_CUSTOM_PARSERS[0x5A])
def _auto_5A(ctx, a):
    return _generic_emit("UPDATE_EVENT_POSITION")(ctx, a)


@op(
    0x5B,
    "LOAD_EXT_SCHEDULER",
    operands=[
        ("scheduler_work_offset", "u16"),
        ("entity1_id", "u32"),
        ("entity2_id", "u32"),
        ("action_id", "u32"),
    ],
)
def _auto_5B(ctx, a):
    return _generic_emit(
        "LOAD_EXT_SCHEDULER",
        (
            ("scheduler_work_offset", "u16"),
            ("entity1_id", "u32"),
            ("entity2_id", "u32"),
            ("action_id", "u32"),
        ),
    )(ctx, a)


@op(0x5C, "MUSIC_CONTROL", custom_parse=_CUSTOM_PARSERS[0x5C])
def _auto_5C(ctx, a):
    return _generic_emit("MUSIC_CONTROL")(ctx, a)


@op(0x5D, "SET_MUSIC_VOLUME", operands=[("volume", "u16"), ("fade_time", "u16")])
def _auto_5D(ctx, a):
    return _generic_emit(
        "SET_MUSIC_VOLUME",
        (
            ("volume", "u16"),
            ("fade_time", "u16"),
        ),
    )(ctx, a)


@op(0x5E, "STOP_ENTITY_ACTION_RESET_IDLE", operands=[("animation_id", "u32")])
def _auto_5E(ctx, a):
    return _generic_emit("STOP_ENTITY_ACTION_RESET_IDLE", (("animation_id", "u32"),))(
        ctx, a
    )


@op(0x5F, "MULTI_HANDLER_COMPLEX", custom_parse=_CUSTOM_PARSERS[0x5F])
def _auto_5F(ctx, a):
    return _generic_emit("MULTI_HANDLER_COMPLEX")(ctx, a)


@op(0x60, "ADJUST_RENDER_FLAGS1_MULTI", custom_parse=_CUSTOM_PARSERS[0x60])
def _auto_60(ctx, a):
    return _generic_emit("ADJUST_RENDER_FLAGS1_MULTI")(ctx, a)


@op(0x61, "ADJUST_RENDER_FLAGS2", operands=[("flag_value", "u8")])
def _auto_61(ctx, a):
    return _generic_emit("ADJUST_RENDER_FLAGS2", (("flag_value", "u8"),))(ctx, a)


@op(
    0x62,
    "LOAD_EVENT_SCHEDULER",
    operands=[
        ("work_offset1", "u16"),
        ("entity1", "u32"),
        ("entity2", "u32"),
        ("scheduler_id", "u32"),
        ("work_offset2", "u16"),
    ],
)
def _auto_62(ctx, a):
    return _generic_emit(
        "LOAD_EVENT_SCHEDULER",
        (
            ("work_offset1", "u16"),
            ("entity1", "u32"),
            ("entity2", "u32"),
            ("scheduler_id", "u32"),
            ("work_offset2", "u16"),
        ),
    )(ctx, a)


@op(0x63, "PLAY_ANIMATION_WAIT", operands=[("animation_id", "u16")])
def _auto_63(ctx, a):
    return _generic_emit("PLAY_ANIMATION_WAIT", (("animation_id", "u16"),))(ctx, a)


@op(
    0x64,
    "CALCULATE_DISTANCE",
    operands=[
        ("dest_offset", "u16"),
        ("x1_offset", "u16"),
        ("z1_offset", "u16"),
        ("x2_offset", "u16"),
        ("z2_offset", "u16"),
    ],
)
def _auto_64(ctx, a):
    return _generic_emit(
        "CALCULATE_DISTANCE",
        (
            ("dest_offset", "u16"),
            ("x1_offset", "u16"),
            ("z1_offset", "u16"),
            ("x2_offset", "u16"),
            ("z2_offset", "u16"),
        ),
    )(ctx, a)


@op(
    0x65,
    "CALCULATE_3D_DISTANCE",
    operands=[("result", "u16"), ("entity1", "u32"), ("entity2", "u32")],
)
def _auto_65(ctx, a):
    return _generic_emit(
        "CALCULATE_3D_DISTANCE",
        (
            ("result", "u16"),
            ("entity1", "u32"),
            ("entity2", "u32"),
        ),
    )(ctx, a)


@op(
    0x66,
    "LOAD_EXT_SCHEDULER_MAIN",
    operands=[
        ("unknown1", "u16"),
        ("entity1_id", "u32"),
        ("entity2_id", "u32"),
        ("action_id", "u32"),
    ],
)
def _auto_66(ctx, a):
    return _generic_emit(
        "LOAD_EXT_SCHEDULER_MAIN",
        (
            ("unknown1", "u16"),
            ("entity1_id", "u32"),
            ("entity2_id", "u32"),
            ("action_id", "u32"),
        ),
    )(ctx, a)


@op(0x67, "HIDE_HUD_ELEMENTS", operands=[("param1", "u16"), ("param2", "u16")])
def _auto_67(ctx, a):
    return _generic_emit(
        "HIDE_HUD_ELEMENTS",
        (
            ("param1", "u16"),
            ("param2", "u16"),
        ),
    )(ctx, a)


@op(0x68, "SHOW_HUD_ELEMENTS")
def _auto_68(ctx, a):
    return _generic_emit("SHOW_HUD_ELEMENTS")(ctx, a)


@op(0x69, "SET_SOUND_VOLUME", operands=[("mute_flag", "u8"), ("sound_types", "u16")])
def _auto_69(ctx, a):
    return _generic_emit(
        "SET_SOUND_VOLUME",
        (
            ("mute_flag", "u8"),
            ("sound_types", "u16"),
        ),
    )(ctx, a)


@op(
    0x6A,
    "CHANGE_SOUND_VOLUME",
    operands=[("volume", "u16"), ("fade_time", "u16"), ("sound_types", "u16")],
)
def _auto_6A(ctx, a):
    return _generic_emit(
        "CHANGE_SOUND_VOLUME",
        (
            ("volume", "u16"),
            ("fade_time", "u16"),
            ("sound_types", "u16"),
        ),
    )(ctx, a)


@op(
    0x6B, "ENTITY_IDLE_MOTION", operands=[("animation_id", "u32"), ("entity_id", "u32")]
)
def _auto_6B(ctx, a):
    return _generic_emit(
        "ENTITY_IDLE_MOTION",
        (
            ("animation_id", "u32"),
            ("entity_id", "u32"),
        ),
    )(ctx, a)


@op(
    0x6C,
    "FADE_ENTITY_COLOR",
    operands=[("entity_id", "u32"), ("end_alpha", "u16"), ("fade_time", "u16")],
)
def _auto_6C(ctx, a):
    return _generic_emit(
        "FADE_ENTITY_COLOR",
        (
            ("entity_id", "u32"),
            ("end_alpha", "u16"),
            ("fade_time", "u16"),
        ),
    )(ctx, a)


@op(
    0x6D,
    "DEPRECATED_OPCODE",
    operands=[("unused1", "u16"), ("unused2", "u16"), ("unused3", "u16")],
)
def _auto_6D(ctx, a):
    return _generic_emit(
        "DEPRECATED_OPCODE",
        (
            ("unused1", "u16"),
            ("unused2", "u16"),
            ("unused3", "u16"),
        ),
    )(ctx, a)


@op(0x6E, "PLAY_EMOTE", operands=[("entity_id", "u32"), ("emote_data", "u16")])
def _auto_6E(ctx, a):
    return _generic_emit(
        "PLAY_EMOTE",
        (
            ("entity_id", "u32"),
            ("emote_data", "u16"),
        ),
    )(ctx, a)


@op(0x6F, "WAIT_FRAME_DELAY")
def _auto_6F(ctx, a):
    return _generic_emit("WAIT_FRAME_DELAY")(ctx, a)


@op(0x70, "WAIT_ENTITY_RENDER_FLAG")
def _auto_70(ctx, a):
    return _generic_emit("WAIT_ENTITY_RENDER_FLAG")(ctx, a)


@op(0x71, "HANDLE_STRING_INPUT", custom_parse=_CUSTOM_PARSERS[0x71])
def _auto_71(ctx, a):
    return _generic_emit("HANDLE_STRING_INPUT")(ctx, a)


@op(0x72, "LOAD_EVENT_WEATHER", custom_parse=_CUSTOM_PARSERS[0x72])
def _auto_72(ctx, a):
    return _generic_emit("LOAD_EVENT_WEATHER")(ctx, a)


@op(
    0x73,
    "SCHEDULE_MAGIC_CASTING",
    operands=[("magic_id", "u16"), ("caster_entity", "u32"), ("target_entity", "u32")],
)
def _auto_73(ctx, a):
    return _generic_emit(
        "SCHEDULE_MAGIC_CASTING",
        (
            ("magic_id", "u16"),
            ("caster_entity", "u32"),
            ("target_entity", "u32"),
        ),
    )(ctx, a)


@op(0x74, "ADJUST_RENDER_FLAGS1", operands=[("flag", "u8")])
def _auto_74(ctx, a):
    return _generic_emit("ADJUST_RENDER_FLAGS1", (("flag", "u8"),))(ctx, a)


@op(0x75, "LOAD_ROOM", custom_parse=_CUSTOM_PARSERS[0x75])
def _auto_75(ctx, a):
    return _generic_emit("LOAD_ROOM")(ctx, a)


@op(0x76, "CHECK_ENTITY_RENDER_FLAGS", operands=[("entity", "u32")])
def _auto_76(ctx, a):
    return _generic_emit("CHECK_ENTITY_RENDER_FLAGS", (("entity", "u32"),))(ctx, a)


@op(0x77, "SET_EVENT_TIME_WEATHER", operands=[("hour", "u16"), ("weather", "u16")])
def _auto_77(ctx, a):
    return _generic_emit(
        "SET_EVENT_TIME_WEATHER",
        (
            ("hour", "u16"),
            ("weather", "u16"),
        ),
    )(ctx, a)


@op(0x78, "ENABLE_GAME_TIMER_RESET_WEATHER")
def _auto_78(ctx, a):
    return _generic_emit("ENABLE_GAME_TIMER_RESET_WEATHER")(ctx, a)


@op(0x79, "LOOK_AT_ENTITY", custom_parse=_CUSTOM_PARSERS[0x79])
def _auto_79(ctx, a):
    return _generic_emit("LOOK_AT_ENTITY")(ctx, a)


@op(0x7A, "VM_CONTROL", custom_parse=_CUSTOM_PARSERS[0x7A])
def _auto_7A(ctx, a):
    return _generic_emit("VM_CONTROL")(ctx, a)


@op(0x7B, "UNSET_ENTITY_TALKING", operands=[("entity_id", "u32")])
def _auto_7B(ctx, a):
    return _generic_emit("UNSET_ENTITY_TALKING", (("entity_id", "u32"),))(ctx, a)


@op(
    0x7C, "ADJUST_RENDER_FLAGS2", operands=[("enable_flag", "u8"), ("entity_id", "u32")]
)
def _auto_7C(ctx, a):
    return _generic_emit(
        "ADJUST_RENDER_FLAGS2",
        (
            ("enable_flag", "u8"),
            ("entity_id", "u32"),
        ),
    )(ctx, a)


@op(0x7D, "LOAD_START_SCHEDULER_PLAYER", operands=[("animation_id", "u16")])
def _auto_7D(ctx, a):
    return _generic_emit("LOAD_START_SCHEDULER_PLAYER", (("animation_id", "u16"),))(
        ctx, a
    )


@op(0x7E, "CHOCOBO_MOUNT_HANDLER", custom_parse=_CUSTOM_PARSERS[0x7E])
def _auto_7E(ctx, a):
    return _generic_emit("CHOCOBO_MOUNT_HANDLER")(ctx, a)


@op(0x7F, "WAIT_DIALOG_SELECT_ALT")
def _auto_7F(ctx, a):
    return _generic_emit("WAIT_DIALOG_SELECT_ALT")(ctx, a)


@op(0x80, "LOAD_WAIT", operands=[("entity", "u32")])
def _auto_80(ctx, a):
    return _generic_emit("LOAD_WAIT", (("entity", "u32"),))(ctx, a)


@op(0x81, "SET_ENTITY_BLINKING", operands=[("blink_flag", "u8"), ("entity", "u32")])
def _auto_81(ctx, a):
    return _generic_emit(
        "SET_ENTITY_BLINKING",
        (
            ("blink_flag", "u8"),
            ("entity", "u32"),
        ),
    )(ctx, a)


@op(
    0x82,
    "RECT_HIT_TEST_BRANCH",
    operands=[("rect_id", "u32"), ("jump_offset", "u16")],
    branches=lambda a: [a.jump_offset],
)
def _auto_82(ctx, a):
    return _generic_emit(
        "RECT_HIT_TEST_BRANCH",
        (
            ("rect_id", "u32"),
            ("jump_offset", "u16"),
        ),
    )(ctx, a)


@op(0x83, "GET_GAME_TIME", operands=[("target", "u16")])
def _auto_83(ctx, a):
    return _generic_emit("GET_GAME_TIME", (("target", "u16"),))(ctx, a)


@op(0x84, "ADJUST_RENDER_FLAGS3_BIT0")
def _auto_84(ctx, a):
    return _generic_emit("ADJUST_RENDER_FLAGS3_BIT0")(ctx, a)


@op(0x85, "OPEN_MOOGLE_MENU")
def _auto_85(ctx, a):
    return _generic_emit("OPEN_MOOGLE_MENU")(ctx, a)


@op(0x86, "ADJUST_RENDER_FLAGS3", operands=[("flag_value", "u8"), ("entity_id", "u32")])
def _auto_86(ctx, a):
    return _generic_emit(
        "ADJUST_RENDER_FLAGS3",
        (
            ("flag_value", "u8"),
            ("entity_id", "u32"),
        ),
    )(ctx, a)


@op(0x87, "WORLD_PASS_HANDLER_A", custom_parse=_CUSTOM_PARSERS[0x87])
def _auto_87(ctx, a):
    return _generic_emit("WORLD_PASS_HANDLER_A")(ctx, a)


@op(0x88, "WORLD_PASS_HANDLER_B", custom_parse=_CUSTOM_PARSERS[0x88])
def _auto_88(ctx, a):
    return _generic_emit("WORLD_PASS_HANDLER_B")(ctx, a)


@op(0x89, "OPEN_MAP", operands=[("map_id", "u16")])
def _auto_89(ctx, a):
    return _generic_emit("OPEN_MAP", (("map_id", "u16"),))(ctx, a)


@op(0x8A, "CLOSE_MAP")
def _auto_8A(ctx, a):
    return _generic_emit("CLOSE_MAP")(ctx, a)


@op(
    0x8B,
    "SET_EVENT_MARK",
    operands=[
        ("map_id", "u16"),
        ("point_index", "u16"),
        ("pos_x", "u16"),
        ("pos_y", "u16"),
    ],
)
def _auto_8B(ctx, a):
    return _generic_emit(
        "SET_EVENT_MARK",
        (
            ("map_id", "u16"),
            ("point_index", "u16"),
            ("pos_x", "u16"),
            ("pos_y", "u16"),
        ),
    )(ctx, a)


@op(0x8C, "CRAFTING_HANDLER", custom_parse=_CUSTOM_PARSERS[0x8C])
def _auto_8C(ctx, a):
    return _generic_emit("CRAFTING_HANDLER")(ctx, a)


@op(
    0x8D,
    "OPEN_MAP_WITH_PROPERTIES",
    operands=[("map_id", "u16"), ("properties", "u16")],
)
def _auto_8D(ctx, a):
    return _generic_emit(
        "OPEN_MAP_WITH_PROPERTIES",
        (
            ("map_id", "u16"),
            ("properties", "u16"),
        ),
    )(ctx, a)


@op(0x8E, "SET_ENTITY_STATUS_EVENT_45")
def _auto_8E(ctx, a):
    return _generic_emit("SET_ENTITY_STATUS_EVENT_45")(ctx, a)


@op(0x8F, "SET_ENTITY_STATUS_EVENT_46")
def _auto_8F(ctx, a):
    return _generic_emit("SET_ENTITY_STATUS_EVENT_46")(ctx, a)


@op(0x90, "ADJUST_ENTITY_RENDER_FLAGS0_FLAGS1")
def _auto_90(ctx, a):
    return _generic_emit("ADJUST_ENTITY_RENDER_FLAGS0_FLAGS1")(ctx, a)


@op(0x91, "SET_MAIN_SPEED_BASE", operands=[("speed_value", "u16")])
def _auto_91(ctx, a):
    return _generic_emit("SET_MAIN_SPEED_BASE", (("speed_value", "u16"),))(ctx, a)


@op(0x92, "ADJUST_RENDER_FLAGS3", operands=[("flag", "u8"), ("entity_id", "u32")])
def _auto_92(ctx, a):
    return _generic_emit(
        "ADJUST_RENDER_FLAGS3",
        (
            ("flag", "u8"),
            ("entity_id", "u32"),
        ),
    )(ctx, a)


@op(0x93, "DISPLAY_ITEM_INFO", operands=[("item_id", "u16")])
def _auto_93(ctx, a):
    return _generic_emit("DISPLAY_ITEM_INFO", (("item_id", "u16"),))(ctx, a)


@op(0x94, "ADJUST_RENDER_FLAGS3_ALT", operands=[("flag", "u8"), ("entity_id", "u32")])
def _auto_94(ctx, a):
    return _generic_emit(
        "ADJUST_RENDER_FLAGS3_ALT",
        (
            ("flag", "u8"),
            ("entity_id", "u32"),
        ),
    )(ctx, a)


@op(0x95, "SETUP_EVENT_NPC", operands=[("npc_param", "u16")])
def _auto_95(ctx, a):
    return _generic_emit("SETUP_EVENT_NPC", (("npc_param", "u16"),))(ctx, a)


@op(0x96, "UNSET_EVENT_NPC")
def _auto_96(ctx, a):
    return _generic_emit("UNSET_EVENT_NPC")(ctx, a)


@op(
    0x97, "SAVE_SET_WIND_VALUES", operands=[("wind_base", "u16"), ("wind_width", "u16")]
)
def _auto_97(ctx, a):
    return _generic_emit(
        "SAVE_SET_WIND_VALUES",
        (
            ("wind_base", "u16"),
            ("wind_width", "u16"),
        ),
    )(ctx, a)


@op(0x98, "YIELD_IF_ZONE_LOADING")
def _auto_98(ctx, a):
    return _generic_emit("YIELD_IF_ZONE_LOADING")(ctx, a)


@op(0x99, "WAIT_ANIMATION", operands=[("entity_id", "u32")])
def _auto_99(ctx, a):
    return _generic_emit("WAIT_ANIMATION", (("entity_id", "u32"),))(ctx, a)


@op(0x9A, "WAIT_MUSIC_SERVER")
def _auto_9A(ctx, a):
    return _generic_emit("WAIT_MUSIC_SERVER")(ctx, a)


@op(0x9B, "WAIT_ENTITY_ANIMATION")
def _auto_9B(ctx, a):
    return _generic_emit("WAIT_ENTITY_ANIMATION")(ctx, a)


@op(0x9C, "STORE_CLIENT_LANGUAGE_ID", operands=[("result", "u16")])
def _auto_9C(ctx, a):
    return _generic_emit("STORE_CLIENT_LANGUAGE_ID", (("result", "u16"),))(ctx, a)


@op(0x9D, "OPCODE_9D", custom_parse=_CUSTOM_PARSERS[0x9D])
def _auto_9D(ctx, a):
    return _generic_emit("OPCODE_9D")(ctx, a)


@op(0x9E, "SET_RECT_EVENT_SEND_FLAG", operands=[("flag_value", "u8")])
def _auto_9E(ctx, a):
    return _generic_emit("SET_RECT_EVENT_SEND_FLAG", (("flag_value", "u8"),))(ctx, a)


@op(
    0x9F,
    "LOAD_SCHEDULED_TASK_ALT",
    operands=[
        ("work_offset1", "u16"),
        ("entity1_id", "u32"),
        ("entity2_id", "u32"),
        ("scheduler_id", "u32"),
        ("work_offset2", "u16"),
    ],
)
def _auto_9F(ctx, a):
    return _generic_emit(
        "LOAD_SCHEDULED_TASK_ALT",
        (
            ("work_offset1", "u16"),
            ("entity1_id", "u32"),
            ("entity2_id", "u32"),
            ("scheduler_id", "u32"),
            ("work_offset2", "u16"),
        ),
    )(ctx, a)


@op(
    0xA0,
    "WAIT_LOAD_SCHEDULER_MAIN_ALT2",
    operands=[
        ("work_offset", "u16"),
        ("entity1_id", "u32"),
        ("entity2_id", "u32"),
        ("scheduler_id", "u32"),
    ],
)
def _auto_A0(ctx, a):
    return _generic_emit(
        "WAIT_LOAD_SCHEDULER_MAIN_ALT2",
        (
            ("work_offset", "u16"),
            ("entity1_id", "u32"),
            ("entity2_id", "u32"),
            ("scheduler_id", "u32"),
        ),
    )(ctx, a)


@op(
    0xA1,
    "END_LOAD_SCHEDULER_MAIN",
    operands=[
        ("work_offset", "u16"),
        ("entity1_id", "u32"),
        ("entity2_id", "u32"),
        ("scheduler_id", "u32"),
    ],
)
def _auto_A1(ctx, a):
    return _generic_emit(
        "END_LOAD_SCHEDULER_MAIN",
        (
            ("work_offset", "u16"),
            ("entity1_id", "u32"),
            ("entity2_id", "u32"),
            ("scheduler_id", "u32"),
        ),
    )(ctx, a)


@op(
    0xA2,
    "WAIT_LOAD_SCHEDULER_MAIN",
    operands=[
        ("work_offset", "u16"),
        ("entity1_id", "u32"),
        ("entity2_id", "u32"),
        ("scheduler_id", "u32"),
    ],
)
def _auto_A2(ctx, a):
    return _generic_emit(
        "WAIT_LOAD_SCHEDULER_MAIN",
        (
            ("work_offset", "u16"),
            ("entity1_id", "u32"),
            ("entity2_id", "u32"),
            ("scheduler_id", "u32"),
        ),
    )(ctx, a)


@op(
    0xA3,
    "END_LOAD_SCHEDULER_MAIN_ALT",
    operands=[
        ("work_offset", "u16"),
        ("entity1_id", "u32"),
        ("entity2_id", "u32"),
        ("scheduler_id", "u32"),
    ],
)
def _auto_A3(ctx, a):
    return _generic_emit(
        "END_LOAD_SCHEDULER_MAIN_ALT",
        (
            ("work_offset", "u16"),
            ("entity1_id", "u32"),
            ("entity2_id", "u32"),
            ("scheduler_id", "u32"),
        ),
    )(ctx, a)


@op(0xA4, "ADJUST_RENDER_FLAGS3_BIT26", operands=[("flag_value", "u8")])
def _auto_A4(ctx, a):
    return _generic_emit("ADJUST_RENDER_FLAGS3_BIT26", (("flag_value", "u8"),))(ctx, a)


@op(0xA5, "ADJUST_RENDER_FLAGS3_BIT11", operands=[("flag_value", "u8")])
def _auto_A5(ctx, a):
    return _generic_emit("ADJUST_RENDER_FLAGS3_BIT11", (("flag_value", "u8"),))(ctx, a)


@op(0xA6, "REQUEST_EVENT_MAP_NUMBER", custom_parse=_CUSTOM_PARSERS[0xA6])
def _auto_A6(ctx, a):
    return _generic_emit("REQUEST_EVENT_MAP_NUMBER")(ctx, a)


@op(0xA7, "BATTLEFIELD_SERVER_RESPONSE_WAIT", custom_parse=_CUSTOM_PARSERS[0xA7])
def _auto_A7(ctx, a):
    return _generic_emit("BATTLEFIELD_SERVER_RESPONSE_WAIT")(ctx, a)


@op(
    0xA8,
    "MAP_MARKER_CONTROL",
    operands=[("map_flag", "u8"), ("zone_offset", "u16"), ("marker_offset", "u16")],
)
def _auto_A8(ctx, a):
    return _generic_emit(
        "MAP_MARKER_CONTROL",
        (
            ("map_flag", "u8"),
            ("zone_offset", "u16"),
            ("marker_offset", "u16"),
        ),
    )(ctx, a)


@op(0xA9, "DISABLE_GAME_TIME_SET_SPECIFIC", operands=[("time_offset", "u16")])
def _auto_A9(ctx, a):
    return _generic_emit("DISABLE_GAME_TIME_SET_SPECIFIC", (("time_offset", "u16"),))(
        ctx, a
    )


@op(
    0xAA,
    "VANA_DIEL_TIMESTAMP_CONVERTER",
    operands=[
        ("timestamp", "u16"),
        ("year", "u16"),
        ("month", "u16"),
        ("day", "u16"),
        ("weekday", "u16"),
        ("hour", "u16"),
        ("minute", "u16"),
        ("moon", "u16"),
    ],
)
def _auto_AA(ctx, a):
    return _generic_emit(
        "VANA_DIEL_TIMESTAMP_CONVERTER",
        (
            ("timestamp", "u16"),
            ("year", "u16"),
            ("month", "u16"),
            ("day", "u16"),
            ("weekday", "u16"),
            ("hour", "u16"),
            ("minute", "u16"),
            ("moon", "u16"),
        ),
    )(ctx, a)


@op(0xAB, "ADJUST_ENTITY_FLAGS", custom_parse=_CUSTOM_PARSERS[0xAB])
def _auto_AB(ctx, a):
    return _generic_emit("ADJUST_ENTITY_FLAGS")(ctx, a)


@op(0xAC, "ENTITY_STATUS_HANDLER", custom_parse=_CUSTOM_PARSERS[0xAC])
def _auto_AC(ctx, a):
    return _generic_emit("ENTITY_STATUS_HANDLER")(ctx, a)


@op(
    0xAD,
    "DUAL_ENTITY_SCHEDULER_HANDLER",
    operands=[
        ("sub_case", "u8"),
        ("param", "u16"),
        ("entity1", "u32"),
        ("entity2", "u32"),
    ],
)
def _auto_AD(ctx, a):
    return _generic_emit(
        "DUAL_ENTITY_SCHEDULER_HANDLER",
        (
            ("sub_case", "u8"),
            ("param", "u16"),
            ("entity1", "u32"),
            ("entity2", "u32"),
        ),
    )(ctx, a)


@op(0xAE, "MULTI_PURPOSE_ENTITY_HANDLER", custom_parse=_CUSTOM_PARSERS[0xAE])
def _auto_AE(ctx, a):
    return _generic_emit("MULTI_PURPOSE_ENTITY_HANDLER")(ctx, a)


@op(
    0xAF,
    "GET_CAMERA_POSITION",
    operands=[("mode", "u8"), ("x", "u16"), ("z", "u16"), ("y", "u16")],
)
def _auto_AF(ctx, a):
    return _generic_emit(
        "GET_CAMERA_POSITION",
        (
            ("mode", "u8"),
            ("x", "u16"),
            ("z", "u16"),
            ("y", "u16"),
        ),
    )(ctx, a)


@op(
    0xB0,
    "PRINT_EVENT_MESSAGE",
    operands=[
        ("unknown1", "u8"),
        ("speaker_id", "u32"),
        ("listener_id", "u32"),
        ("message_offset", "u16"),
    ],
)
def _auto_B0(ctx, a):
    return _generic_emit(
        "PRINT_EVENT_MESSAGE",
        (
            ("unknown1", "u8"),
            ("speaker_id", "u32"),
            ("listener_id", "u32"),
            ("message_offset", "u16"),
        ),
    )(ctx, a)


@op(0xB1, "GET_APP_FLAG", operands=[("flag_type", "u8"), ("dest_offset", "u16")])
def _auto_B1(ctx, a):
    return _generic_emit(
        "GET_APP_FLAG",
        (
            ("flag_type", "u8"),
            ("dest_offset", "u16"),
        ),
    )(ctx, a)


@op(0xB2, "DELIVERY_BOX_HANDLER", operands=[("mode", "u8")])
def _auto_B2(ctx, a):
    return _generic_emit("DELIVERY_BOX_HANDLER", (("mode", "u8"),))(ctx, a)


@op(0xB3, "RANKINGS_BOARD_HANDLER", operands=[("case_type", "u8")])
def _auto_B3(ctx, a):
    return _generic_emit("RANKINGS_BOARD_HANDLER", (("case_type", "u8"),))(ctx, a)


@op(0xB4, "UI_WINDOW_STRING_HANDLER", custom_parse=_CUSTOM_PARSERS[0xB4])
def _auto_B4(ctx, a):
    return _generic_emit("UI_WINDOW_STRING_HANDLER")(ctx, a)


@op(0xB5, "SET_EVENT_ENTITY_NAME", operands=[("mode", "u8"), ("name_string", "u16")])
def _auto_B5(ctx, a):
    return _generic_emit(
        "SET_EVENT_ENTITY_NAME",
        (
            ("mode", "u8"),
            ("name_string", "u16"),
        ),
    )(ctx, a)


@op(0xB6, "ENTITY_APPEARANCE_HANDLER", custom_parse=_CUSTOM_PARSERS[0xB6])
def _auto_B6(ctx, a):
    return _generic_emit("ENTITY_APPEARANCE_HANDLER")(ctx, a)


@op(0xB7, "ENTITY_DATA_HANDLER", custom_parse=_CUSTOM_PARSERS[0xB7])
def _auto_B7(ctx, a):
    return _generic_emit("ENTITY_DATA_HANDLER")(ctx, a)


@op(0xB8, "MAP_ADD_MARKER_WITH_NAME")
def _auto_B8(ctx, a):
    return _generic_emit("MAP_ADD_MARKER_WITH_NAME")(ctx, a)


@op(
    0xB9,
    "MAP_EDIT_MARKER_FROM_BUFFER",
    operands=[
        ("map_flag", "u8"),
        ("zone", "u16"),
        ("submap", "u16"),
        ("marker_id", "u16"),
    ],
)
def _auto_B9(ctx, a):
    return _generic_emit(
        "MAP_EDIT_MARKER_FROM_BUFFER",
        (
            ("map_flag", "u8"),
            ("zone", "u16"),
            ("submap", "u16"),
            ("marker_id", "u16"),
        ),
    )(ctx, a)


@op(
    0xBA,
    "SET_ENTITY_POSITION",
    operands=[
        ("entity_id", "u32"),
        ("pos_x", "u16"),
        ("pos_z", "u16"),
        ("pos_y", "u16"),
        ("direction", "u16"),
    ],
)
def _auto_BA(ctx, a):
    return _generic_emit(
        "SET_ENTITY_POSITION",
        (
            ("entity_id", "u32"),
            ("pos_x", "u16"),
            ("pos_z", "u16"),
            ("pos_y", "u16"),
            ("direction", "u16"),
        ),
    )(ctx, a)


@op(
    0xBB,
    "LOAD_EVENT_SCHEDULER_ALT",
    operands=[
        ("work_offset1", "u16"),
        ("entity1_id", "u32"),
        ("entity2_id", "u32"),
        ("scheduler_id", "u32"),
        ("work_offset2", "u16"),
    ],
)
def _auto_BB(ctx, a):
    return _generic_emit(
        "LOAD_EVENT_SCHEDULER_ALT",
        (
            ("work_offset1", "u16"),
            ("entity1_id", "u32"),
            ("entity2_id", "u32"),
            ("scheduler_id", "u32"),
            ("work_offset2", "u16"),
        ),
    )(ctx, a)


@op(
    0xBC,
    "WAIT_LOAD_SCHEDULER_ALT2",
    operands=[
        ("work_offset", "u16"),
        ("entity1_id", "u32"),
        ("entity2_id", "u32"),
        ("scheduler_id", "u32"),
    ],
)
def _auto_BC(ctx, a):
    return _generic_emit(
        "WAIT_LOAD_SCHEDULER_ALT2",
        (
            ("work_offset", "u16"),
            ("entity1_id", "u32"),
            ("entity2_id", "u32"),
            ("scheduler_id", "u32"),
        ),
    )(ctx, a)


@op(
    0xBD,
    "END_LOAD_SCHEDULER_MAIN_ALT6",
    operands=[
        ("work_offset", "u16"),
        ("entity1_id", "u32"),
        ("entity2_id", "u32"),
        ("scheduler_id", "u32"),
    ],
)
def _auto_BD(ctx, a):
    return _generic_emit(
        "END_LOAD_SCHEDULER_MAIN_ALT6",
        (
            ("work_offset", "u16"),
            ("entity1_id", "u32"),
            ("entity2_id", "u32"),
            ("scheduler_id", "u32"),
        ),
    )(ctx, a)


@op(0xBE, "STORE_REQ_WHO_SERVER_ID", operands=[("work_offset", "u16")])
def _auto_BE(ctx, a):
    return _generic_emit("STORE_REQ_WHO_SERVER_ID", (("work_offset", "u16"),))(ctx, a)


@op(0xBF, "CHOCOBO_RACING_PARAMETER_GETTER", operands=[("param_type", "u8")])
def _auto_BF(ctx, a):
    return _generic_emit("CHOCOBO_RACING_PARAMETER_GETTER", (("param_type", "u8"),))(
        ctx, a
    )


@op(0xC0, "ADJUST_RENDER_FLAGS3_BIT12", operands=[("flag_value", "u16")])
def _auto_C0(ctx, a):
    return _generic_emit("ADJUST_RENDER_FLAGS3_BIT12", (("flag_value", "u16"),))(ctx, a)


@op(0xC1, "KILL_ENTITY_ACTION", operands=[("entity_id", "u32")])
def _auto_C1(ctx, a):
    return _generic_emit("KILL_ENTITY_ACTION", (("entity_id", "u32"),))(ctx, a)


@op(0xC2, "PARTY_STATE_CHECK", custom_parse=_CUSTOM_PARSERS[0xC2])
def _auto_C2(ctx, a):
    return _generic_emit("PARTY_STATE_CHECK")(ctx, a)


@op(
    0xC3,
    "COPY_STRING_TO_ARRAY",
    operands=[
        ("array_index", "u16"),
        ("string_value", "u16"),
        ("additional_value", "u16"),
    ],
)
def _auto_C3(ctx, a):
    return _generic_emit(
        "COPY_STRING_TO_ARRAY",
        (
            ("array_index", "u16"),
            ("string_value", "u16"),
            ("additional_value", "u16"),
        ),
    )(ctx, a)


@op(
    0xC4,
    "HELPER_CALL_ALT",
    operands=[
        ("mode", "u8"),
        ("magic_id", "u16"),
        ("caster_entity", "u32"),
        ("target_entity", "u32"),
    ],
)
def _auto_C4(ctx, a):
    return _generic_emit(
        "HELPER_CALL_ALT",
        (
            ("mode", "u8"),
            ("magic_id", "u16"),
            ("caster_entity", "u32"),
            ("target_entity", "u32"),
        ),
    )(ctx, a)


@op(
    0xC5,
    "LOAD_SCHEDULED_TASK_ALT3",
    operands=[
        ("work_offset", "u16"),
        ("entity1_id", "u32"),
        ("entity2_id", "u32"),
        ("task_param", "u16"),
        ("scheduler_id", "u32"),
    ],
)
def _auto_C5(ctx, a):
    return _generic_emit(
        "LOAD_SCHEDULED_TASK_ALT3",
        (
            ("work_offset", "u16"),
            ("entity1_id", "u32"),
            ("entity2_id", "u32"),
            ("task_param", "u16"),
            ("scheduler_id", "u32"),
        ),
    )(ctx, a)


@op(
    0xC6,
    "WAIT_LOAD_SCHEDULER_ALT3",
    operands=[
        ("work_offset", "u16"),
        ("entity1_id", "u32"),
        ("entity2_id", "u32"),
        ("scheduler_id", "u32"),
    ],
)
def _auto_C6(ctx, a):
    return _generic_emit(
        "WAIT_LOAD_SCHEDULER_ALT3",
        (
            ("work_offset", "u16"),
            ("entity1_id", "u32"),
            ("entity2_id", "u32"),
            ("scheduler_id", "u32"),
        ),
    )(ctx, a)


@op(
    0xC7,
    "END_LOAD_SCHEDULER_ALT3",
    operands=[
        ("work_offset", "u16"),
        ("entity1_id", "u32"),
        ("entity2_id", "u32"),
        ("scheduler_id", "u32"),
    ],
)
def _auto_C7(ctx, a):
    return _generic_emit(
        "END_LOAD_SCHEDULER_ALT3",
        (
            ("work_offset", "u16"),
            ("entity1_id", "u32"),
            ("entity2_id", "u32"),
            ("scheduler_id", "u32"),
        ),
    )(ctx, a)


@op(
    0xC8,
    "OPEN_MAP_WINDOW",
    operands=[("zone", "u16"), ("submap", "u16"), ("flag", "u16")],
)
def _auto_C8(ctx, a):
    return _generic_emit(
        "OPEN_MAP_WINDOW",
        (
            ("zone", "u16"),
            ("submap", "u16"),
            ("flag", "u16"),
        ),
    )(ctx, a)


@op(0xC9, "ENABLE_GAME_TIMER")
def _auto_C9(ctx, a):
    return _generic_emit("ENABLE_GAME_TIMER")(ctx, a)


@op(0xCA, "DEPRECATED_OPCODE_CA", custom_parse=_CUSTOM_PARSERS[0xCA])
def _auto_CA(ctx, a):
    return _generic_emit("DEPRECATED_OPCODE_CA")(ctx, a)


@op(0xCB, "DEPRECATED_OPCODE_CB", custom_parse=_CUSTOM_PARSERS[0xCB])
def _auto_CB(ctx, a):
    return _generic_emit("DEPRECATED_OPCODE_CB")(ctx, a)


@op(0xCC, "ITEM_INFO_WINDOW_HANDLER", custom_parse=_CUSTOM_PARSERS[0xCC])
def _auto_CC(ctx, a):
    return _generic_emit("ITEM_INFO_WINDOW_HANDLER")(ctx, a)


@op(
    0xCD,
    "LOAD_SCHEDULED_TASK_ALT4",
    operands=[
        ("work_offset1", "u16"),
        ("entity1_id", "u32"),
        ("entity2_id", "u32"),
        ("scheduler_id", "u32"),
        ("work_offset2", "u16"),
    ],
)
def _auto_CD(ctx, a):
    return _generic_emit(
        "LOAD_SCHEDULED_TASK_ALT4",
        (
            ("work_offset1", "u16"),
            ("entity1_id", "u32"),
            ("entity2_id", "u32"),
            ("scheduler_id", "u32"),
            ("work_offset2", "u16"),
        ),
    )(ctx, a)


@op(
    0xCE,
    "WAIT_LOAD_SCHEDULER_ALT4",
    operands=[
        ("work_offset", "u16"),
        ("entity1", "u32"),
        ("entity2", "u32"),
        ("scheduler_id", "u32"),
    ],
)
def _auto_CE(ctx, a):
    return _generic_emit(
        "WAIT_LOAD_SCHEDULER_ALT4",
        (
            ("work_offset", "u16"),
            ("entity1", "u32"),
            ("entity2", "u32"),
            ("scheduler_id", "u32"),
        ),
    )(ctx, a)


@op(
    0xCF,
    "END_LOAD_SCHEDULER_ALT4",
    operands=[
        ("work_offset", "u16"),
        ("entity1_id", "u32"),
        ("entity2_id", "u32"),
        ("scheduler_id", "u32"),
    ],
)
def _auto_CF(ctx, a):
    return _generic_emit(
        "END_LOAD_SCHEDULER_ALT4",
        (
            ("work_offset", "u16"),
            ("entity1_id", "u32"),
            ("entity2_id", "u32"),
            ("scheduler_id", "u32"),
        ),
    )(ctx, a)


@op(
    0xD0,
    "LOAD_SCHEDULED_TASK_ALT5",
    operands=[
        ("work_offset1", "u16"),
        ("entity1_id", "u32"),
        ("entity2_id", "u32"),
        ("scheduler_id", "u32"),
        ("work_offset2", "u16"),
    ],
)
def _auto_D0(ctx, a):
    return _generic_emit(
        "LOAD_SCHEDULED_TASK_ALT5",
        (
            ("work_offset1", "u16"),
            ("entity1_id", "u32"),
            ("entity2_id", "u32"),
            ("scheduler_id", "u32"),
            ("work_offset2", "u16"),
        ),
    )(ctx, a)


@op(
    0xD1,
    "WAIT_LOAD_SCHEDULER_ALT5",
    operands=[
        ("work_offset", "u16"),
        ("entity1", "u32"),
        ("entity2", "u32"),
        ("scheduler_id", "u32"),
    ],
)
def _auto_D1(ctx, a):
    return _generic_emit(
        "WAIT_LOAD_SCHEDULER_ALT5",
        (
            ("work_offset", "u16"),
            ("entity1", "u32"),
            ("entity2", "u32"),
            ("scheduler_id", "u32"),
        ),
    )(ctx, a)


@op(
    0xD2,
    "END_LOAD_SCHEDULER_MAIN_ALT7",
    operands=[
        ("unknown1", "u8"),
        ("unknown2", "u8"),
        ("entity1_id", "u32"),
        ("entity2_id", "u32"),
        ("scheduler_param", "u16"),
        ("unknown3", "u8"),
        ("work_offset", "u8"),
    ],
)
def _auto_D2(ctx, a):
    return _generic_emit(
        "END_LOAD_SCHEDULER_MAIN_ALT7",
        (
            ("unknown1", "u8"),
            ("unknown2", "u8"),
            ("entity1_id", "u32"),
            ("entity2_id", "u32"),
            ("scheduler_param", "u16"),
            ("unknown3", "u8"),
            ("work_offset", "u8"),
        ),
    )(ctx, a)


@op(
    0xD3,
    "CLEAR_ENTITY_MOTION_QUEUE",
    operands=[("condition_flag", "u8"), ("entity_server_id", "u32")],
)
def _auto_D3(ctx, a):
    return _generic_emit(
        "CLEAR_ENTITY_MOTION_QUEUE",
        (
            ("condition_flag", "u8"),
            ("entity_server_id", "u32"),
        ),
    )(ctx, a)


@op(0xD4, "MAP_QUERY_WINDOW_HANDLER", custom_parse=_CUSTOM_PARSERS[0xD4])
def _auto_D4(ctx, a):
    return _generic_emit("MAP_QUERY_WINDOW_HANDLER")(ctx, a)


@op(
    0xD5,
    "LOAD_EVENT_SCHEDULER_ALT8",
    operands=[
        ("unknown1", "u8"),
        ("unknown2", "u8"),
        ("entity1_id", "u32"),
        ("entity2_id", "u32"),
        ("task_param", "u16"),
        ("unknown3", "u8"),
        ("unknown4", "u8"),
        ("work_offset", "u8"),
        ("unknown5", "u8"),
    ],
)
def _auto_D5(ctx, a):
    return _generic_emit(
        "LOAD_EVENT_SCHEDULER_ALT8",
        (
            ("unknown1", "u8"),
            ("unknown2", "u8"),
            ("entity1_id", "u32"),
            ("entity2_id", "u32"),
            ("task_param", "u16"),
            ("unknown3", "u8"),
            ("unknown4", "u8"),
            ("work_offset", "u8"),
            ("unknown5", "u8"),
        ),
    )(ctx, a)


@op(
    0xD6,
    "WAIT_LOAD_SCHEDULER_ALT6",
    operands=[
        ("work_offset", "u16"),
        ("entity1_id", "u32"),
        ("entity2_id", "u32"),
        ("scheduler_id", "u32"),
    ],
)
def _auto_D6(ctx, a):
    return _generic_emit(
        "WAIT_LOAD_SCHEDULER_ALT6",
        (
            ("work_offset", "u16"),
            ("entity1_id", "u32"),
            ("entity2_id", "u32"),
            ("scheduler_id", "u32"),
        ),
    )(ctx, a)


@op(
    0xD7,
    "END_LOAD_SCHEDULER_ALT6",
    operands=[
        ("work_offset", "u16"),
        ("entity1_id", "u32"),
        ("entity2_id", "u32"),
        ("scheduler_id", "u32"),
    ],
)
def _auto_D7(ctx, a):
    return _generic_emit(
        "END_LOAD_SCHEDULER_ALT6",
        (
            ("work_offset", "u16"),
            ("entity1_id", "u32"),
            ("entity2_id", "u32"),
            ("scheduler_id", "u32"),
        ),
    )(ctx, a)


@op(0xD8, "SET_ENTITY_EVENT_DIR", custom_parse=_CUSTOM_PARSERS[0xD8])
def _auto_D8(ctx, a):
    return _generic_emit("SET_ENTITY_EVENT_DIR")(ctx, a)


@op(0xD9, "SET_SOUND_EFFECT_LIMIT_FLAG", operands=[("flag_value", "u8")])
def _auto_D9(ctx, a):
    return _generic_emit("SET_SOUND_EFFECT_LIMIT_FLAG", (("flag_value", "u8"),))(ctx, a)
