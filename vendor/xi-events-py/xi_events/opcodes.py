"""Hand-refined opcode emit functions. Override the placeholders in
opcodes_auto.py via the OPS-dict overwrite in registry.op."""

from __future__ import annotations

import struct
from typing import Callable

from luaparser import astnodes as N

from . import work_area as W
from .custom_parsers import PARSERS as _CUSTOM_PARSERS
from .registry import op


def _scheduler_args(
    ctx, a, *, work_attr: str | None = "work", second_work_attr: str | None = None
) -> list:
    e1 = ctx.entity(a.entity1)
    e2 = ctx.entity(a.entity2)
    args: list = [W.lua_string(W.action_id(a.scheduler_id))]
    if isinstance(e1, N.Name) and isinstance(e2, N.Name) and e1.id == e2.id:
        args.append(e1)
    else:
        args.extend([e1, e2])
    if work_attr is not None:
        args.append(ctx.value(getattr(a, work_attr)))
    if second_work_attr is not None:
        args.append(ctx.value(getattr(a, second_work_attr)))
    return args


def _scheduler(
    method: str, *, work_attr: str | None = "work", second_work_attr: str | None = None
):
    def emit(ctx, a):
        return ctx.invoke(
            "npc",
            method,
            _scheduler_args(
                ctx, a, work_attr=work_attr, second_work_attr=second_work_attr
            ),
        )

    return emit


def _compound_assign(
    ctx, dest_addr: int, op_cls, source_node: N.Expression
) -> N.Assign:
    target = ctx.value(dest_addr)
    return N.Assign(
        targets=[target], values=[op_cls(left=ctx.value(dest_addr), right=source_node)]
    )


def _cmp_eq(lhs, rhs):
    return N.EqToOp(left=lhs, right=rhs)


def _cmp_le(lhs, rhs):
    return N.LessOrEqThanOp(left=lhs, right=rhs)


def _cmp_ge(lhs, rhs):
    return N.GreaterOrEqThanOp(left=lhs, right=rhs)


def _cmp_lt(lhs, rhs):
    return N.LessThanOp(left=lhs, right=rhs)


def _cmp_gt(lhs, rhs):
    return N.GreaterThanOp(left=lhs, right=rhs)


def _cmp_bit(op_cls):
    def cmp(lhs, rhs):
        return N.NotEqToOp(left=op_cls(left=lhs, right=rhs), right=N.Number(0))

    return cmp


_CMP_DISPATCH: dict[int, Callable[[N.Expression, N.Expression], N.Expression]] = {
    0x0: _cmp_eq,
    0x1: _cmp_eq,
    0x7: _cmp_eq,
    0x2: _cmp_le,
    0x3: _cmp_ge,
    0x4: _cmp_lt,
    0x5: _cmp_gt,
    0x6: _cmp_bit(N.BAndOp),
    0x8: _cmp_bit(N.BOrOp),
    0x9: _cmp_bit(N.BAndOp),
    0xA: _cmp_bit(N.BXorOp),
}


@op(0x00, "END_REQSTACK", terminal=True)
def end_reqstack(ctx, a):
    return N.Return(values=[])


@op(
    0x01,
    "GOTO",
    operands=[("target", "u16")],
    terminal=True,
    branches=lambda a: [a.target],
)
def goto(ctx, a):
    return None


def _imed_ref(addr: int) -> N.Expression:
    return N.Index(
        idx=N.Number(addr & 0x7FFF),
        value=N.Name("imed"),
        notation=N.IndexNotation.SQUARE,
    )


def _cond_operands(ctx, lhs: int, rhs: int) -> tuple:
    """Render the two operands of an IF_CONDITIONAL.

    When BOTH operands are in the IMED range, ``ctx.value`` would inline
    each to its stored literal — producing nonsense like ``if 6 == 0 then``
    where the original Lua compared two stored values from the imed pool.
    De-inline both as ``imed[N]`` references in that case so the comparison
    stays semantically meaningful and matches the ``-- imed:`` header.

    Otherwise (one work-area + one imed, or both work-area), the standard
    inlining is correct: ``if result == 0 then`` reads better than
    ``if result == imed[2] then``.
    """
    lhs_is_imed = 0x8000 <= lhs <= 0x8FFF
    rhs_is_imed = 0x8000 <= rhs <= 0x8FFF
    if lhs_is_imed and rhs_is_imed:
        return _imed_ref(lhs), _imed_ref(rhs)
    return ctx.value(lhs), ctx.value(rhs)


@op(
    0x02,
    "IF_CONDITIONAL",
    operands=[("lhs", "u16"), ("rhs", "u16"), ("cond", "u8"), ("else_target", "u16")],
    branches=lambda a: [a.else_target],
)
def if_conditional(ctx, a):
    cmp_fn = _CMP_DISPATCH.get(a.cond & 0x0F, _cmp_eq)
    lhs, rhs = _cond_operands(ctx, a.lhs, a.rhs)
    return cmp_fn(lhs, rhs)


@op(0x21, "END_EVENT")
def end_event(ctx, a):
    return N.Return(values=[])


@op(0x1A, "JUMP_TO_POSITION", operands=[("target", "u16")])
def jump_to_position(ctx, a):
    # Subroutine call. Not a conditional/branch — control returns inline
    # after RETURN_FROM_JUMP. We don't follow into the sub during disasm.
    return N.Call(
        func=N.Name(f"sub_{a.target:04X}"),
        args=[N.Name("npc"), N.Name("player"), N.Name("params")],
    )


@op(0x1B, "RETURN_FROM_JUMP", terminal=True)
def return_from_jump(ctx, a):
    return N.Return(values=[])


@op(
    0x3E,
    "TEST_BIT_AND_BRANCH",
    operands=[("target", "u16"), ("bit_index", "u16"), ("else_target", "u16")],
    branches=lambda a: [a.else_target],
)
def test_bit_and_branch(ctx, a):
    call = N.Call(
        func=N.Name("bit_test"), args=[ctx.value(a.target), ctx.value(a.bit_index)]
    )
    return N.NotEqToOp(left=call, right=N.Number(0))


@op(
    0x44,
    "IF_ENTITY_VALID",
    operands=[("entity", "u16"), ("else_target", "u16")],
    branches=lambda a: [a.else_target],
)
def if_entity_valid(ctx, a):
    return N.Call(func=N.Name("entity_valid"), args=[ctx.value(a.entity)])


@op(0x03, "COPY_WORK_VALUE", operands=[("dest", "u16"), ("source", "u16")])
def copy_work_value(ctx, a):
    return N.Assign(targets=[ctx.value(a.dest)], values=[ctx.value(a.source)])


@op(0x05, "SET_ONE", operands=[("target", "u16")])
def set_one(ctx, a):
    return N.Assign(targets=[ctx.value(a.target)], values=[N.Number(1)])


@op(0x06, "SET_ZERO", operands=[("target", "u16")])
def set_zero(ctx, a):
    return N.Assign(targets=[ctx.value(a.target)], values=[N.Number(0)])


@op(0x07, "ADD_VALUES", operands=[("dest", "u16"), ("source", "u16")])
def add_values(ctx, a):
    return _compound_assign(ctx, a.dest, N.AddOp, ctx.value(a.source))


@op(0x08, "SUBTRACT_VALUES", operands=[("dest", "u16"), ("source", "u16")])
def subtract_values(ctx, a):
    return _compound_assign(ctx, a.dest, N.SubOp, ctx.value(a.source))


@op(0x14, "MULTIPLY_VALUES", operands=[("dest", "u16"), ("source", "u16")])
def multiply_values(ctx, a):
    return _compound_assign(ctx, a.dest, N.MultOp, ctx.value(a.source))


@op(0x15, "DIVIDE_VALUES", operands=[("dest", "u16"), ("source", "u16")])
def divide_values(ctx, a):
    return _compound_assign(ctx, a.dest, N.FloatDivOp, ctx.value(a.source))


@op(
    0x3F,
    "MODULO_OPERATION",
    operands=[("target", "u16"), ("dividend", "u16"), ("divisor", "u16")],
)
def modulo_operation(ctx, a):
    return N.Assign(
        targets=[ctx.value(a.target)],
        values=[N.ModOp(left=ctx.value(a.dividend), right=ctx.value(a.divisor))],
    )


@op(0x12, "GENERATE_RANDOM", operands=[("target", "u16")])
def generate_random(ctx, a):
    return N.Assign(
        targets=[ctx.value(a.target)],
        values=[N.Call(func=N.Name("math.random"), args=[])],
    )


@op(0x13, "GENERATE_RANDOM_RANGE", operands=[("target", "u16"), ("max_value", "u16")])
def generate_random_range(ctx, a):
    return N.Assign(
        targets=[ctx.value(a.target)],
        values=[N.Call(func=N.Name("math.random"), args=[ctx.value(a.max_value)])],
    )


@op(
    0x36,
    "SET_ENTITY_EVENT_POSITION",
    operands=[("x", "u16"), ("z", "u16"), ("y", "u16")],
)
def set_entity_event_position(ctx, a):
    return ctx.invoke(
        "vm",
        "setEntityEventPosition",
        [ctx.coord(a.x), ctx.coord(a.z), ctx.coord(a.y)],
    )


@op(
    0x3A,
    "CONVERT_YAW_TO_BYTE",
    operands=[("entity_id", "u32"), ("result_destination", "u16")],
)
def convert_yaw_to_byte(ctx, a):
    return N.Assign(
        targets=[ctx.value(a.result_destination)],
        values=[ctx.invoke("vm", "convertYawToByte", [ctx.entity(a.entity_id)])],
    )


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
def get_entity_position(ctx, a):
    return N.Assign(
        targets=[
            ctx.value(a.x_destination),
            ctx.value(a.y_destination),
            ctx.value(a.z_destination),
        ],
        values=[ctx.invoke("vm", "getEntityPosition", [ctx.entity(a.entity_id)])],
    )


@op(0x0D, "BITWISE_AND", operands=[("dest", "u16"), ("source", "u16")])
def bitwise_and(ctx, a):
    return _compound_assign(ctx, a.dest, N.BAndOp, ctx.value(a.source))


@op(0x0E, "BITWISE_OR", operands=[("dest", "u16"), ("source", "u16")])
def bitwise_or(ctx, a):
    return _compound_assign(ctx, a.dest, N.BOrOp, ctx.value(a.source))


@op(0x0F, "BITWISE_XOR", operands=[("dest", "u16"), ("source", "u16")])
def bitwise_xor(ctx, a):
    return _compound_assign(ctx, a.dest, N.BXorOp, ctx.value(a.source))


@op(0x10, "BITWISE_LEFT_SHIFT", operands=[("dest", "u16"), ("source", "u16")])
def bitwise_lshift(ctx, a):
    return _compound_assign(ctx, a.dest, N.BShiftLOp, ctx.value(a.source))


@op(0x11, "BITWISE_RIGHT_SHIFT", operands=[("dest", "u16"), ("source", "u16")])
def bitwise_rshift(ctx, a):
    return _compound_assign(ctx, a.dest, N.BShiftROp, ctx.value(a.source))


@op(0x0B, "INCREMENT_VALUE", operands=[("target", "u16")])
def increment_value(ctx, a):
    return _compound_assign(ctx, a.target, N.AddOp, N.Number(1))


@op(0x0C, "DECREMENT_VALUE", operands=[("target", "u16")])
def decrement_value(ctx, a):
    return _compound_assign(ctx, a.target, N.SubOp, N.Number(1))


def _bit_assign(ctx, fn_name: str, target_addr: int, bit_addr: int) -> N.Assign:
    target = ctx.value(target_addr)
    return N.Assign(
        targets=[target],
        values=[
            N.Call(func=N.Name(fn_name), args=[target, ctx.value(bit_addr)]),
        ],
    )


@op(0x09, "SET_BIT_FLAG", operands=[("target", "u16"), ("bit", "u16")])
def set_bit_flag(ctx, a):
    return _bit_assign(ctx, "bit_set", a.target, a.bit)


@op(0x0A, "CLEAR_BIT_FLAG", operands=[("target", "u16"), ("bit", "u16")])
def clear_bit_flag(ctx, a):
    return _bit_assign(ctx, "bit_clear", a.target, a.bit)


@op(
    0x3C,
    "SET_BIT_FLAG_CONDITIONAL",
    operands=[("target", "u16"), ("bit", "u16"), ("condition", "u16")],
)
def set_bit_flag_conditional(ctx, a):
    return _bit_conditional(ctx, "bit_set", a.target, a.bit, a.condition)


@op(
    0x3D,
    "CLEAR_BIT_FLAG_CONDITIONAL",
    operands=[("target", "u16"), ("bit", "u16"), ("condition", "u16")],
)
def clear_bit_flag_conditional(ctx, a):
    return _bit_conditional(ctx, "bit_clear", a.target, a.bit, a.condition)


def _bit_conditional(ctx, fn_name, target, bit, condition) -> N.Statement:
    body = _bit_assign(ctx, fn_name, target, bit)
    cond_node = ctx.value(condition)
    # Skip the wrapper for trivially-true literal conditions (very common).
    if isinstance(cond_node, N.Number) and cond_node.n != 0:
        return body
    return N.If(
        test=N.NotEqToOp(left=cond_node, right=N.Number(0)),
        body=N.Block(body=[body]),
        orelse=None,
    )


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
def set_bit_work_range(ctx, a):
    return N.Assign(
        targets=[ctx.value(a.target)],
        values=[
            N.Call(
                func=N.Name("bit_range_set"),
                args=[
                    ctx.value(a.target),
                    ctx.value(a.start_bit),
                    ctx.value(a.end_bit),
                    ctx.value(a.source),
                ],
            )
        ],
    )


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
def get_bit_work_range(ctx, a):
    return N.Assign(
        targets=[ctx.value(a.result)],
        values=[
            N.Call(
                func=N.Name("bit_range_get"),
                args=[
                    ctx.value(a.source),
                    ctx.value(a.start_bit),
                    ctx.value(a.end_bit),
                ],
            )
        ],
    )


@op(0x1D, "PRINT_EVENT_MESSAGE", operands=[("message", "u16")])
def print_event_message(ctx, a):
    return ctx.invoke("npc", "say", [ctx.value(a.message)])


@op(0x23, "WAIT_FOR_DIALOG_INTERACTION")
def wait_for_dialog_interaction(ctx, a):
    return ctx.invoke("player", "waitForKeypress", [])


@op(
    0x24,
    "CREATE_DIALOG",
    operands=[("message", "u16"), ("default_option", "u16"), ("option_flags", "u16")],
)
def create_dialog(ctx, a):
    return N.Assign(
        targets=[N.Name("result")],
        values=[
            ctx.invoke(
                "npc",
                "dialog",
                [
                    ctx.value(a.message),
                    ctx.value(a.default_option),
                    ctx.value(a.option_flags),
                ],
            )
        ],
    )


@op(0x25, "WAIT_DIALOG_SELECT")
def wait_dialog_select(ctx, a):
    return None  # CREATE_DIALOG already produced ``result = npc:dialog(...)``


@op(0x48, "PRINT_MESSAGE", operands=[("message", "u16")])
def print_message(ctx, a):
    return ctx.invoke("vm", "systemMessage", [ctx.value(a.message)])


@op(0x2B, "PRINT_ENTITY_MESSAGE", operands=[("entity", "u32"), ("message", "u16")])
def print_entity_message(ctx, a):
    return N.Invoke(
        source=ctx.entity(a.entity),
        func=N.Name("say"),
        args=[ctx.value(a.message)],
    )


@op(0x1C, "WAIT_TIME", operands=[("ticks", "u16")])
def wait_time(ctx, a):
    return ctx.invoke("vm", "wait", [ctx.value(a.ticks)])


@op(0x6F, "WAIT_FRAME_DELAY")
def wait_frame_delay(ctx, a):
    return ctx.invoke("vm", "waitFrameDelay", [])


@op(0x70, "WAIT_ENTITY_RENDER_FLAG")
def wait_entity_render_flag(ctx, a):
    return ctx.invoke("vm", "waitEntityRenderFlag", [])


@op(0x20, "SET_CLI_EVENT_UC_FLAG", operands=[("flag", "u8")])
def set_cli_event_uc_flag(ctx, a):
    method = "lockControls" if a.flag == 1 else "unlockControls"
    return ctx.invoke("player", method, [])


@op(0x42, "SET_CLI_EVENT_CANCEL_DATA")
def set_cli_event_cancel_data(ctx, a):
    return ctx.invoke("player", "setCancelData", [])


@op(0x1E, "ENTITY_LOOK_AT_AND_TALK", operands=[("target", "u32")])
def entity_look_at_and_talk(ctx, a):
    return ctx.invoke("npc", "lookAtAndTalk", [ctx.entity(a.target)])


@op(0x4A, "ENTITY_LOOK_AT", operands=[("looker", "u32"), ("target", "u32")])
def entity_look_at(ctx, a):
    return N.Invoke(
        source=ctx.entity(a.looker),
        func=N.Name("lookAt"),
        args=[ctx.entity(a.target)],
    )


from .custom_parsers import parse_look_at_entity as _parse_look_at_entity


@op(0x79, "LOOK_AT_ENTITY", custom_parse=_parse_look_at_entity)
def look_at_entity(ctx, a):
    args: list = []
    if hasattr(a, "target"):
        args.append(ctx.entity(a.target))
    if hasattr(a, "work"):
        args.append(ctx.value(a.work))
    return N.Invoke(
        source=ctx.entity(a.looker) if hasattr(a, "looker") else N.Name("vm"),
        func=N.Name("lookAt"),
        args=args,
    )


@op(0x4E, "SET_ENTITY_HIDE_FLAG", operands=[("flag", "u8"), ("entity", "u32")])
def set_entity_hide_flag(ctx, a):
    method = "hide" if a.flag else "show"
    return N.Invoke(source=ctx.entity(a.entity), func=N.Name(method), args=[])


@op(0x5E, "STOP_ENTITY_ACTION_RESET_IDLE", operands=[("animation", "u32")])
def stop_entity_action_reset_idle(ctx, a):
    return ctx.invoke("npc", "goIdle", [W.lua_string(W.action_id(a.animation))])


@op(
    0x37,
    "UPDATE_EVENT_POSITION_AND_DIR",
    operands=[("x", "u16"), ("z", "u16"), ("y", "u16"), ("dir", "u16")],
)
def update_event_position_and_dir(ctx, a):
    return ctx.invoke(
        "vm",
        "updateEventPositionAndDir",
        [ctx.coord(a.x), ctx.coord(a.z), ctx.coord(a.y), ctx.yaw(a.dir)],
    )


@op(0x39, "SET_ENTITY_DIRECTION", operands=[("direction", "u16")])
def set_entity_direction(ctx, a):
    return ctx.invoke("npc", "setDirection", [ctx.yaw(a.direction)])


@op(0x4B, "UPDATE_ENTITY_YAW", operands=[("entity", "u32"), ("yaw", "u16")])
def update_entity_yaw(ctx, a):
    return N.Invoke(
        source=ctx.entity(a.entity),
        func=N.Name("setYaw"),
        args=[ctx.yaw(a.yaw)],
    )


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
def set_event_mark(ctx, a):
    return ctx.invoke(
        "vm",
        "setEventMark",
        [
            ctx.value(a.map_id),
            ctx.value(a.point_index),
            ctx.coord(a.pos_x),
            ctx.coord(a.pos_y),
        ],
    )


@op(
    0xAF,
    "GET_CAMERA_POSITION",
    operands=[("mode", "u8"), ("x", "u16"), ("z", "u16"), ("y", "u16")],
)
def get_camera_position(ctx, a):
    return ctx.invoke(
        "vm",
        "getCameraPosition",
        [N.Number(a.mode), ctx.coord(a.x), ctx.coord(a.z), ctx.coord(a.y)],
    )


from .custom_parsers import (
    parse_move_entity as _parse_move_entity,
    parse_update_entity_position as _parse_update_entity_position,
    parse_update_event_position as _parse_update_event_position,
)


@op(0x1F, "MOVE_ENTITY", custom_parse=_parse_move_entity)
def move_entity(ctx, a):
    if a.mode == 0 and hasattr(a, "x"):
        return ctx.invoke(
            "npc",
            "moveTo",
            [ctx.coord(a.x), ctx.coord(a.z), ctx.coord(a.y)],
        )
    return ctx.invoke("npc", "moveUpdate", [N.Number(a.mode)])


@op(0x31, "UPDATE_ENTITY_POSITION", custom_parse=_parse_update_entity_position)
def update_entity_position(ctx, a):
    if a.mode == 0 and hasattr(a, "x"):
        return ctx.invoke(
            "npc",
            "setGoalPosition",
            [
                ctx.coord(a.x),
                ctx.coord(a.z),
                ctx.coord(a.y),
                ctx.value(a.move_time),
            ],
        )
    return ctx.invoke("npc", "moveTowardGoal", [])


@op(0x5A, "UPDATE_EVENT_POSITION", custom_parse=_parse_update_event_position)
def update_event_position(ctx, a):
    if a.mode == 0 and hasattr(a, "x"):
        return ctx.invoke(
            "vm",
            "updateEventPosition",
            [ctx.coord(a.x), ctx.coord(a.z), ctx.coord(a.y)],
        )
    return ctx.invoke("vm", "updateEventPosition", [N.Number(a.mode)])


@op(
    0xBA,
    "SET_ENTITY_POSITION",
    operands=[
        ("entity", "u32"),
        ("x", "u16"),
        ("z", "u16"),
        ("y", "u16"),
        ("direction", "u16"),
    ],
)
def set_entity_position(ctx, a):
    return N.Invoke(
        source=ctx.entity(a.entity),
        func=N.Name("setPosition"),
        args=[ctx.coord(a.x), ctx.coord(a.z), ctx.coord(a.y), ctx.yaw(a.direction)],
    )


@op(0x80, "LOAD_WAIT", operands=[("entity", "u32")])
def load_wait(ctx, a):
    return N.Invoke(source=ctx.entity(a.entity), func=N.Name("waitForLoad"), args=[])


def _entity_flag_method(
    method: str, flag_attr: str = "flag", entity_attr: str = "entity"
):
    def emit(ctx, a):
        return N.Invoke(
            source=ctx.entity(getattr(a, entity_attr)),
            func=N.Name(method),
            args=[N.Number(getattr(a, flag_attr))],
        )

    return emit


op(0x92, "ADJUST_RENDER_FLAGS3", operands=[("flag", "u8"), ("entity", "u32")])(
    _entity_flag_method("adjustRenderFlags")
)

op(0x94, "ADJUST_RENDER_FLAGS3_ALT", operands=[("flag", "u8"), ("entity", "u32")])(
    _entity_flag_method("adjustRenderFlagsAlt")
)

op(0x2F, "ADJUST_RENDER_FLAGS0", operands=[("flag", "u8"), ("entity_id", "u32")])(
    _entity_flag_method("adjustRenderFlags0", entity_attr="entity_id")
)

op(
    0x7C, "ADJUST_RENDER_FLAGS2", operands=[("enable_flag", "u8"), ("entity_id", "u32")]
)(
    _entity_flag_method(
        "adjustRenderFlags2", flag_attr="enable_flag", entity_attr="entity_id"
    )
)


@op(0x93, "DISPLAY_ITEM_INFO", operands=[("item", "u16")])
def display_item_info(ctx, a):
    return ctx.invoke("vm", "displayItemInfo", [ctx.value(a.item)])


op(
    0x5B,
    "LOAD_EXT_SCHEDULER",
    operands=[
        ("work", "u16"),
        ("entity1", "u32"),
        ("entity2", "u32"),
        ("scheduler_id", "u32"),
    ],
)(_scheduler("loadExtScheduler"))

op(
    0x52,
    "END_LOAD_SCHEDULER",
    operands=[
        ("work", "u16"),
        ("entity1", "u32"),
        ("entity2", "u32"),
        ("scheduler_id", "u32"),
    ],
)(_scheduler("endScheduler"))

op(
    0x53,
    "WAIT_SCHEDULER_TASK",
    operands=[
        ("entity1", "u32"),
        ("entity2", "u32"),
        ("scheduler_id", "u32"),
    ],
)(_scheduler("waitScheduler", work_attr=None))

op(
    0x55,
    "WAIT_LOAD_SCHEDULER",
    operands=[
        ("work", "u16"),
        ("entity1", "u32"),
        ("entity2", "u32"),
        ("scheduler_id", "u32"),
    ],
)(_scheduler("waitLoadScheduler"))

op(
    0x66,
    "LOAD_EXT_SCHEDULER_MAIN",
    operands=[
        ("work", "u16"),
        ("entity1", "u32"),
        ("entity2", "u32"),
        ("scheduler_id", "u32"),
    ],
)(_scheduler("loadExtSchedulerMain"))

op(
    0x45,
    "LOAD_SCHEDULED_TASK",
    operands=[
        ("work", "u16"),
        ("entity1", "u32"),
        ("entity2", "u32"),
        ("scheduler_id", "u32"),
        ("work2", "u16"),
    ],
)(_scheduler("loadScheduledTask", second_work_attr="work2"))


op(
    0x2C,
    "CREATE_SCHEDULER_TASK",
    operands=[("entity1", "u32"), ("entity2", "u32"), ("scheduler_id", "u32")],
)(_scheduler("createSchedulerTask", work_attr=None))


op(
    0x2D,
    "CREATE_ZONE_SCHEDULER_TASK",
    operands=[("entity1", "u32"), ("entity2", "u32"), ("scheduler_id", "u32")],
)(_scheduler("createZoneSchedulerTask", work_attr=None))


# Map-scheduler pair: 3 u32 (entity1, entity2, scheduler_id), no work.
op(
    0x51,
    "END_MAP_SCHEDULER",
    operands=[("entity1", "u32"), ("entity2", "u32"), ("scheduler_id", "u32")],
)(_scheduler("endMapScheduler", work_attr=None))


op(
    0x54,
    "WAIT_MAP_SCHEDULER",
    operands=[("entity1", "u32"), ("entity2", "u32"), ("scheduler_id", "u32")],
)(_scheduler("waitMapScheduler", work_attr=None))


# WAIT/END LOAD_SCHEDULER ALT variants — all share the (work, entity1,
# entity2, scheduler_id) shape that _scheduler already handles. Registering
# them collapses ~15 vm:methodAltN(work, e1, e2, sched) calls into the
# idiomatic npc:methodAltN("name", entity, work) form.

_LOAD_SCHEDULED_TASK_ALTS = [
    (0x9F, "LOAD_SCHEDULED_TASK_ALT", "loadScheduledTaskAlt"),
    (0xCD, "LOAD_SCHEDULED_TASK_ALT4", "loadScheduledTaskAlt4"),
    (0xD0, "LOAD_SCHEDULED_TASK_ALT5", "loadScheduledTaskAlt5"),
]
for _code, _opname, _method in _LOAD_SCHEDULED_TASK_ALTS:
    op(
        _code,
        _opname,
        operands=[
            ("work", "u16"),
            ("entity1", "u32"),
            ("entity2", "u32"),
            ("scheduler_id", "u32"),
            ("work2", "u16"),
        ],
    )(_scheduler(_method, second_work_attr="work2"))


_LOAD_SCHEDULER_ALTS = [
    (0xA0, "WAIT_LOAD_SCHEDULER_MAIN_ALT2", "waitLoadSchedulerMainAlt2"),
    (0xA1, "END_LOAD_SCHEDULER_MAIN", "endLoadSchedulerMain"),
    (0xA2, "WAIT_LOAD_SCHEDULER_MAIN", "waitLoadSchedulerMain"),
    (0xA3, "END_LOAD_SCHEDULER_MAIN_ALT", "endLoadSchedulerMainAlt"),
    (0xBC, "WAIT_LOAD_SCHEDULER_ALT2", "waitLoadSchedulerAlt2"),
    (0xBD, "END_LOAD_SCHEDULER_MAIN_ALT6", "endLoadSchedulerMainAlt6"),
    (0xC6, "WAIT_LOAD_SCHEDULER_ALT3", "waitLoadSchedulerAlt3"),
    (0xC7, "END_LOAD_SCHEDULER_ALT3", "endLoadSchedulerAlt3"),
    (0xCE, "WAIT_LOAD_SCHEDULER_ALT4", "waitLoadSchedulerAlt4"),
    (0xCF, "END_LOAD_SCHEDULER_ALT4", "endLoadSchedulerAlt4"),
    (0xD1, "WAIT_LOAD_SCHEDULER_ALT5", "waitLoadSchedulerAlt5"),
    (0xD6, "WAIT_LOAD_SCHEDULER_ALT6", "waitLoadSchedulerAlt6"),
    (0xD7, "END_LOAD_SCHEDULER_ALT6", "endLoadSchedulerAlt6"),
]
for _code, _opname, _method in _LOAD_SCHEDULER_ALTS:
    op(
        _code,
        _opname,
        operands=[
            ("work", "u16"),
            ("entity1", "u32"),
            ("entity2", "u32"),
            ("scheduler_id", "u32"),
        ],
    )(_scheduler(_method))


@op(0x9C, "STORE_CLIENT_LANGUAGE_ID", operands=[("result", "u16")])
def store_client_language_id(ctx, a):
    return N.Assign(
        targets=[ctx.value(a.result)],
        values=[ctx.invoke("vm", "getClientLanguageId", [])],
    )


@op(0x22, "ENTITY_HIDE_FLAG", operands=[("enabled", "u8")])
def entity_hide_flag(ctx, a):
    method = "hide" if a.enabled else "show"
    return N.Invoke(source=N.Name("npc"), func=N.Name(method), args=[])


@op(
    0x65,
    "CALCULATE_3D_DISTANCE",
    operands=[("result", "u16"), ("entity1", "u32"), ("entity2", "u32")],
)
def calculate_3d_distance(ctx, a):
    return N.Assign(
        targets=[ctx.value(a.result)],
        values=[
            ctx.invoke(
                "vm",
                "distance3d",
                [ctx.entity(a.entity1), ctx.entity(a.entity2)],
            )
        ],
    )


def _id_or_ref(ctx, value: int) -> N.Expression:
    """Render a u16 as a literal id (e.g. magic_id=122) when below the
    work-area base, or as an imed/work-area reference when high."""
    if value >= 0x1000:
        return ctx.value(value)
    return N.Number(value)


@op(
    0x73,
    "SCHEDULE_MAGIC_CASTING",
    operands=[
        ("magic_id", "u16"),
        ("caster_entity", "u32"),
        ("target_entity", "u32"),
    ],
)
def schedule_magic_casting(ctx, a):
    return N.Invoke(
        source=ctx.entity(a.caster_entity),
        func=N.Name("castMagic"),
        args=[_id_or_ref(ctx, a.magic_id), ctx.entity(a.target_entity)],
    )


_CRAFTING_SIZES = {0: 8, 1: 2, 2: 12, 3: 10, 4: 10, 5: 14}
_CRAFTING_METHODS = {
    0: "initialize",
    1: "endSession",
    2: "setRecipe",
    3: "getSynthRecipe",
    4: "getCrystalRecipe",
    5: "setExtendedRecipe",
}


def _parse_crafting_handler(data: bytes, pos: int) -> tuple[int, dict]:
    mode = data[pos + 1] if pos + 1 < len(data) else 0
    return _CRAFTING_SIZES.get(mode, 2), {"mode": mode}


@op(0x8C, "CRAFTING_HANDLER", custom_parse=_parse_crafting_handler)
def crafting_handler(ctx, a):
    return ctx.invoke(
        "crafting", _CRAFTING_METHODS.get(a.mode, f"mode_0x{a.mode:02X}"), []
    )


def _parse_update_player_location(data: bytes, pos: int) -> tuple[int, dict]:
    if pos + 2 > len(data):
        return 1, {"mode": 0}
    mode = data[pos + 1]
    if mode == 0 and pos + 10 <= len(data):
        x, z, y, yaw = struct.unpack_from("<HHHH", data, pos + 2)
        return 10, {"mode": mode, "x": x, "z": z, "y": y, "yaw": yaw}
    return 2, {"mode": mode}


@op(0x47, "UPDATE_PLAYER_LOCATION", custom_parse=_parse_update_player_location)
def update_player_location(ctx, a):
    if a.mode != 0:
        return ctx.invoke("player", "waitForPositionUpdate", [])
    return ctx.invoke(
        "player",
        "setPosition",
        [
            ctx.coord(a.x),
            ctx.coord(a.z),
            ctx.coord(a.y),
            ctx.yaw(a.yaw),
        ],
    )


_MUSIC_SLOT_NAMES = {
    0: "idle_day",
    1: "idle_night",
    2: "combat_solo",
    3: "combat_party",
    4: "mount",
    5: "death",
}


def _parse_music_control(data: bytes, pos: int) -> tuple[int, dict]:
    if pos + 2 > len(data):
        return 1, {"control": 0, "song": 0}
    control = data[pos + 1]
    long_form = bool(control & 0x80) or control >= 0xA0
    size = 6 if long_form else 4
    if pos + size > len(data):
        return min(size, len(data) - pos), {"control": control, "song": 0}
    song = struct.unpack_from("<H", data, pos + 2)[0]
    out = {"control": control, "song": song}
    if long_form:
        out["aux"] = struct.unpack_from("<H", data, pos + 4)[0]
    return size, out


@op(0x5C, "MUSIC_CONTROL", custom_parse=_parse_music_control)
def music_control(ctx, a):
    control = a.control
    song = ctx.value(a.song)
    aux = ctx.value(a.aux) if hasattr(a, "aux") else N.Number(0)
    if control < 0x08:
        slot = _MUSIC_SLOT_NAMES.get(control, f"slot_{control}")
        return ctx.invoke("vm", "musicSet", [W.lua_string(slot), song])
    if 0x80 <= control <= 0x87:
        slot = _MUSIC_SLOT_NAMES.get(control - 0x80, f"slot_{control - 0x80}")
        return ctx.invoke("vm", "musicSetWithVolume", [W.lua_string(slot), song, aux])
    if control in (0xA0, 0xA1):
        method = "musicVolume" if control == 0xA0 else "musicVolumeAdjust"
        return ctx.invoke("vm", method, [song, aux])
    return ctx.invoke("vm", "musicControl", [N.Number(control), song])


@op(0x43, "SEND_EVENT_UPDATE", operands=[("flag", "u8")])
def send_event_update(ctx, a):
    if a.flag == 0:
        return ctx.invoke("vm", "sendUpdate", [])
    if a.flag == 1:
        return ctx.invoke("vm", "checkPending", [])
    return ctx.invoke("vm", "sendUpdateRaw", [N.Number(a.flag)])


@op(0x27, "REQ_SET", operands=[("priority", "u8"), ("entity", "u32"), ("tag", "u8")])
def req_set(ctx, a):
    return N.Invoke(
        source=ctx.entity(a.entity),
        func=N.Name("reqSet"),
        args=[N.Number(a.priority), N.Number(a.tag)],
    )


@op(
    0x29,
    "REQ_SET_WAIT",
    operands=[
        ("priority", "u8"),
        ("server_id1", "u16"),
        ("server_id2", "u16"),
        ("tag", "u8"),
    ],
)
def req_set_wait(ctx, a):
    eid = (a.server_id2 << 16) | a.server_id1
    return N.Invoke(
        source=ctx.entity(eid),
        func=N.Name("reqSetWait"),
        args=[N.Number(a.priority), N.Number(a.tag)],
    )


@op(0x2A, "GET_REQ_LEVEL", operands=[("level", "u8"), ("entity", "u32")])
def get_req_level(ctx, a):
    return N.Invoke(
        source=ctx.entity(a.entity),
        func=N.Name("getReqLevel"),
        args=[N.Number(a.level)],
    )


@op(0x9D, "OPCODE_9D", custom_parse=_CUSTOM_PARSERS[0x9D])
def opcode_9d(ctx, a):
    """0x9D — string/UI dispatcher with ~17 mode-byte cases. Each case has a
    fixed-size operand block whose semantics aren't documented in any public
    catalog; render every word so refining a specific case is just renaming
    the function and re-labeling args.

    The mode byte becomes the function-name suffix (``opcode9D_modeXX``).
    Across observed modes the first word is a scalar key/id (in ranges that
    aren't valid work-area addresses). The remaining words are typically
    work-area or imed (``0x80xx``) references — those go through ``ctx.value``
    so they resolve to ``scratch[N] / params[N] / state[N] / <imed value>``."""
    words = getattr(a, "words", ())
    fn = f"opcode9D_mode{a.mode:02X}"
    args: list = []
    for i, w in enumerate(words):
        if isinstance(w, str):
            args.append(W.lua_string(w))
        elif i == 0 and isinstance(w, int):
            args.append(N.Number(w))
        elif isinstance(w, int):
            args.append(ctx.value(w))
        else:
            args.append(N.Number(w))
    return ctx.invoke("vm", fn, args)


# Math write-back ops: result = math.fn(...). The opcode result is the FFXI
# integer-scaled trig output — input is encoded angle, multiplier scales the
# float back to integer. Decompose as `math.sin(input) * multiplier` so the
# semantics are transparent in plain Lua.


def _trig_emit(fn_name: str):
    def emit(ctx, a):
        call = N.Call(func=N.Name(fn_name), args=[ctx.value(a.input)])
        return N.Assign(
            targets=[ctx.value(a.result)],
            values=[N.MultOp(left=call, right=ctx.value(a.multiplier))],
        )

    return emit


op(
    0x16,
    "SINE_CALCULATION",
    operands=[("result", "u16"), ("input", "u16"), ("multiplier", "u16")],
)(_trig_emit("math.sin"))


op(
    0x17,
    "COSINE_CALCULATION",
    operands=[("result", "u16"), ("input", "u16"), ("multiplier", "u16")],
)(_trig_emit("math.cos"))


@op(
    0x18,
    "ATAN2_CALCULATION",
    operands=[("result", "u16"), ("y_input", "u16"), ("x_input", "u16")],
)
def atan2_calculation(ctx, a):
    return N.Assign(
        targets=[ctx.value(a.result)],
        values=[
            N.Call(
                func=N.Name("math.atan2"),
                args=[ctx.value(a.y_input), ctx.value(a.x_input)],
            )
        ],
    )


@op(0x83, "GET_GAME_TIME", operands=[("target", "u16")])
def get_game_time(ctx, a):
    return N.Assign(
        targets=[ctx.value(a.target)],
        values=[ctx.invoke("vm", "getGameTime", [])],
    )


# Single-entity action opcodes: render as entity:method(args) instead of
# vm:opName(entity, args). The entity is the natural receiver.


@op(
    0x6B, "ENTITY_IDLE_MOTION", operands=[("animation_id", "u32"), ("entity_id", "u32")]
)
def entity_idle_motion(ctx, a):
    return N.Invoke(
        source=ctx.entity(a.entity_id),
        func=N.Name("idleMotion"),
        args=[W.lua_string(W.action_id(a.animation_id))],
    )


@op(
    0x6C,
    "FADE_ENTITY_COLOR",
    operands=[("entity_id", "u32"), ("end_alpha", "u16"), ("fade_time", "u16")],
)
def fade_entity_color(ctx, a):
    return N.Invoke(
        source=ctx.entity(a.entity_id),
        func=N.Name("fadeColor"),
        args=[ctx.value(a.end_alpha), ctx.value(a.fade_time)],
    )


@op(0x6E, "PLAY_EMOTE", operands=[("entity_id", "u32"), ("emote_data", "u16")])
def play_emote(ctx, a):
    return N.Invoke(
        source=ctx.entity(a.entity_id),
        func=N.Name("playEmote"),
        args=[ctx.value(a.emote_data)],
    )


@op(0x7B, "UNSET_ENTITY_TALKING", operands=[("entity_id", "u32")])
def unset_entity_talking(ctx, a):
    return N.Invoke(
        source=ctx.entity(a.entity_id),
        func=N.Name("unsetTalking"),
        args=[],
    )


@op(0x81, "SET_ENTITY_BLINKING", operands=[("blink_flag", "u8"), ("entity", "u32")])
def set_entity_blinking(ctx, a):
    return N.Invoke(
        source=ctx.entity(a.entity),
        func=N.Name("setBlinking"),
        args=[N.Number(a.blink_flag)],
    )


def _entity_method(method: str, entity_attr: str = "entity_id"):
    def emit(ctx, a):
        return N.Invoke(
            source=ctx.entity(getattr(a, entity_attr)),
            func=N.Name(method),
            args=[],
        )

    return emit


op(0x76, "CHECK_ENTITY_RENDER_FLAGS", operands=[("entity", "u32")])(
    _entity_method("checkRenderFlags", entity_attr="entity")
)

op(0x99, "WAIT_ANIMATION", operands=[("entity_id", "u32")])(
    _entity_method("waitAnimation")
)

op(0xC1, "KILL_ENTITY_ACTION", operands=[("entity_id", "u32")])(
    _entity_method("killAction")
)


@op(
    0x49,
    "PRINT_EVENT_MESSAGE_NO_SPEAKER",
    operands=[("target_entity", "u32"), ("message_id", "u16")],
)
def print_event_message_no_speaker(ctx, a):
    return N.Invoke(
        source=ctx.entity(a.target_entity),
        func=N.Name("printNoSpeaker"),
        args=[ctx.value(a.message_id)],
    )
