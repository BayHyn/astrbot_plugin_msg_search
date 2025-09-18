from typing import Any
from astrbot.api.star import Context, Star, register
from astrbot.core.config.astrbot_config import AstrBotConfig
from astrbot.api.event import filter
from astrbot.core.message.components import Plain, Reply
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import (
    AiocqhttpMessageEvent,
)
from .utils import get_at_id


@register("astrbot_plugin_msg_search", "Zhalslar", "...", "...")
class MsgSearchPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.conf = config

    def find_last_at_me(
        self,
        target_id: str,
        round_messages: list[dict[str, Any]],
        current_msg_id: str | int | None = None,
        idx: int = 1,
    ) -> str | None:
        """
        返回本轮历史记录中「倒数第 idx 条」@目标的消息 ID
        """
        hit = 0
        for msg in reversed(round_messages):
            # 跳过自己这条命令
            if current_msg_id and str(msg["message_id"]) == str(current_msg_id):
                continue
            for seg in msg["message"]:
                if seg["type"] == "at" and str(seg["data"]["qq"]) == target_id:
                    hit += 1
                    if hit == idx:  # 命中次数够了
                        return msg["message_id"]
        return None

    def find_last_text(
        self,
        target_text: str,
        round_messages: list[dict[str, Any]],
        current_msg_id: str | int | None = None,
        idx: int = 1,
    ) -> str | None:
        """
        返回本轮历史记录中「倒数第 idx 条」包含目标文本的消息 ID
        """
        hit = 0
        for msg in reversed(round_messages):
            # 跳过自己这条命令
            if current_msg_id and str(msg["message_id"]) == str(current_msg_id):
                continue
            for seg in msg["message"]:
                if seg["type"] == "text" and target_text in seg["data"]["text"]:
                    hit += 1
                    if hit == idx:  # 命中次数够了
                        return msg["message_id"]
        return None

    async def get_at_msg_id(
        self,
        event: AiocqhttpMessageEvent,
        target_id: str | None = None,
        target_text: str | None = None,
        idx: int = 1,
        max_query_rounds: int | None = None,
    ) -> str | None:
        """持续获取群聊历史消息直到达到要求"""
        group_id = event.get_group_id()
        message_seq = 0
        max_query_rounds = max_query_rounds or self.conf["max_query_rounds"]
        for _ in range(max_query_rounds):
            payloads = {
                "group_id": group_id,
                "message_seq": message_seq,
                "count": self.conf["per_msg_count"],
                "reverseOrder": True,
            }
            result: dict = await event.bot.api.call_action(
                "get_group_msg_history", **payloads
            )
            round_messages = result["messages"]
            if not round_messages:
                return
            if target_id:
                if at_msg_id := self.find_last_at_me(
                    round_messages=round_messages,
                    target_id=target_id,
                    current_msg_id=event.message_obj.message_id,
                    idx=idx,
                ):
                    return at_msg_id
            elif target_text:
                if at_msg_id := self.find_last_text(
                    round_messages=round_messages,
                    target_text=target_text,
                    current_msg_id=event.message_obj.message_id,
                    idx=idx,
                ):
                    return at_msg_id
            message_seq = round_messages[0]["message_id"]

    @filter.command("谁at我")
    async def search_at(
        self,
        event: AiocqhttpMessageEvent,
        idx: int = 1,
        max_query_rounds: int | None = None,
        target_str: str | None = None,
    ):
        """搜索本群中谁@我，并引用该消息"""
        target_id: str = await get_at_id(event) or event.get_sender_id()

        at_msg_id = await self.get_at_msg_id(
            event, target_id=target_id, idx=idx, max_query_rounds=max_query_rounds
        )

        if not at_msg_id:
            at_str = "你" if target_id == event.get_sender_id() else target_str
            yield event.plain_result(f"没有人{at_str}")
            return
        yield event.chain_result([Reply(id=at_msg_id), Plain(text="↑")])

    @filter.command("搜消息")
    async def search_text(
        self,
        event: AiocqhttpMessageEvent,
        text: str,
        idx: int = 1,
        max_query_rounds: int | None = None,
    ):
        """搜消息 <文本> <序号> <最大查询轮数>"""
        at_msg_id = await self.get_at_msg_id(
            event, target_text=text, idx=idx, max_query_rounds=max_query_rounds
        )

        if not at_msg_id:
            yield event.plain_result("没有搜索到任何相关消息")
            return
        yield event.chain_result([Reply(id=at_msg_id), Plain(text="↑")])
