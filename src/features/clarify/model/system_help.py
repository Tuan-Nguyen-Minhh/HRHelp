"""Approved product Q&A. This module selects answers, never graph routes."""

import re
import unicodedata
from enum import StrEnum

from src.core.config import settings


class HelpTopic(StrEnum):
    IDENTITY = "identity"
    CAPABILITIES = "capabilities"
    AUTHORITY = "authority_limits"
    START = "getting_started"
    WORKFLOW = "workflow_overview"
    MINUTES = "minutes_help"
    ROLES = "roles"
    RETURN = "return_process"
    SOURCES = "sources"
    RELIABILITY = "reliability"
    PRIVACY = "privacy"
    CONVERSATION = "conversation_scope"


def fold_text(text: str) -> str:
    return " ".join(
        "".join(
            c for c in unicodedata.normalize("NFD", text.casefold().replace("đ", "d")) if not unicodedata.combining(c)
        ).split()
    )


_PATTERNS = {
    HelpTopic.AUTHORITY: r"quyet dinh thay|phe duyet|ky duyet|quyen|tham quyen|tu duyet|ky quyet dinh",
    HelpTopic.IDENTITY: r"ban la ai|ten (cua )?ban|tro ly gi|he thong gi",
    HelpTopic.PRIVACY: r"bao mat|rieng tu|du lieu ca nhan|luu du lieu|gui du lieu",
    HelpTopic.RELIABILITY: r"100\s*%|chac chan|chinh xac|tin cay|co sai",
    HelpTopic.RETURN: r"tra lai|khong duyet|bi tu choi|gui lai",
    HelpTopic.MINUTES: r"bien ban|xuat word|xuat docx",
    HelpTopic.ROLES: r"vai tro|quan ly|phap che|nhan su|nguoi ky",
    HelpTopic.SOURCES: r"nguon|tra web|tim web|internet|noi bo",
    HelpTopic.START: r"bat dau|dung the nao|su dung|huong dan",
    HelpTopic.WORKFLOW: r"quy trinh|cac buoc|luong xu ly",
    HelpTopic.CONVERSATION: r"noi chuyen|tro chuyen|ngoai ho so",
    HelpTopic.CAPABILITIES: r"chuc nang|tinh nang|lam duoc|giup.*gi|ho tro.*gi",
}

_ANSWERS = {
    HelpTopic.IDENTITY: "Mình là trợ lý AI trong HR Help, hỗ trợ bạn xử lý hồ sơ kỷ luật lao động. Mình không phải người có thẩm quyền ra quyết định.",
    HelpTopic.CAPABILITIES: "Mình có thể giúp làm rõ và xác nhận tình tiết, xem lại thông tin hồ sơ, tra căn cứ nội bộ, chuẩn bị biên bản và phiếu pháp chế để bạn kiểm tra. Việc gửi, xét duyệt và ban hành vẫn theo quyền và điều kiện của hồ sơ.",
    HelpTopic.AUTHORITY: "Mình có thể hỗ trợ phân tích và chuẩn bị nội dung, nhưng không quyết định thay bạn, tự phê duyệt, ký hay bỏ qua bước xét duyệt. Quyết định chính thức do người có thẩm quyền thực hiện tại chức năng tương ứng trong hệ thống.",
    HelpTopic.START: "Bạn có thể tạo hoặc mở hồ sơ được phép truy cập, cung cấp thông tin sự việc rồi kiểm tra và xác nhận tình tiết. Khi cần, hãy yêu cầu lập biên bản; hệ thống sẽ hỏi thêm thông tin còn thiếu.",
    HelpTopic.WORKFLOW: "Luồng chính gồm thu thập và xác nhận tình tiết → đối chiếu căn cứ, chuẩn bị đánh giá/biên bản → HR kiểm tra bản nháp → chuyển xét duyệt theo luồng được hỗ trợ → người có thẩm quyền quyết định. Chat không tự thay thế các bước xét duyệt.",
    HelpTopic.MINUTES: "HR có thể xem, sửa và xác nhận bản nháp biên bản, rồi xuất Word hoặc chuẩn bị gửi xét duyệt khi hồ sơ đủ điều kiện. Nếu chưa đủ thông tin, hệ thống sẽ nêu phần cần bổ sung; mình không tự xác nhận thay HR.",
    HelpTopic.ROLES: "HR chuẩn bị hồ sơ và kiểm tra biên bản; pháp chế xem xét căn cứ và gửi kết luận; quản lý thực hiện xét duyệt cuối theo quyền. Hệ thống còn có vai trò người ký và quản trị. Các thao tác thực tế phụ thuộc quyền tài khoản và trạng thái hồ sơ.",
    HelpTopic.RETURN: "Khi hồ sơ bị trả lại, HR xem lý do của pháp chế hoặc quản lý, mở bản nháp để sửa, kiểm tra và xác nhận lại trước khi gửi tiếp. Việc hỏi hướng dẫn ở đây không tự sửa hoặc gửi hồ sơ.",
    HelpTopic.RELIABILITY: "Mình có thể hiểu sai hoặc thiếu thông tin, nên không thể cam kết chính xác 100%. Bạn cần đối chiếu nội dung với hồ sơ và nguồn trích dẫn; AI không thay thế trách nhiệm quyết định của người có thẩm quyền.",
    HelpTopic.PRIVACY: "Hệ thống có kiểm tra quyền truy cập hồ sơ và lưu hội thoại phục vụ xử lý. Nội dung cần thiết có thể được gửi tới nhà cung cấp model đang cấu hình. Mình không thể hứa bảo mật tuyệt đối hoặc không lưu dữ liệu; bạn nên tránh gửi mật khẩu và thông tin nhạy cảm không cần thiết.",
}


def resolve_help_topics(question: str, topics: list[HelpTopic] | None = None) -> list[HelpTopic]:
    selected = list(dict.fromkeys(topics or []))
    return selected[:3]


def answer_system_help(question: str, topics: list[HelpTopic] | None = None) -> str:
    if not settings.SYSTEM_HELP_ENABLED:
        return "Chức năng hỏi đáp về hệ thống hiện đang tạm tắt."
    selected = resolve_help_topics(question, topics)
    if not selected:
        folded = fold_text(question)
        selected = [topic for topic, pattern in _PATTERNS.items() if re.search(r"\b(?:" + pattern + r")\b", folded)]
    if not selected:
        return "Bạn muốn tìm hiểu chức năng, cách bắt đầu, quy trình hay giới hạn quyền hạn của trợ lý?"
    answers = []
    for topic in selected[:3]:
        if topic == HelpTopic.SOURCES:
            provider_ready = {
                "brave": bool(settings.BRAVE_SEARCH_API_KEY),
                "tavily": bool(settings.TAVILY_API_KEY),
                "mcp_http": bool(settings.EXTERNAL_RESEARCH_MCP_URL.strip()),
            }.get(settings.EXTERNAL_RESEARCH_PROVIDER, False)
            external = (
                "Tra cứu nguồn công khai đang được bật, với phạm vi nguồn được cấu hình."
                if settings.EXTERNAL_RESEARCH_ENABLED and provider_ready
                else "Tra cứu nguồn công khai hiện chưa được bật hoặc chưa đủ cấu hình."
            )
            answers.append(
                "Mình phân biệt thông tin đang lưu trong hồ sơ với căn cứ từ nội quy/văn bản được truy xuất. "
                + external
                + " Một câu hỏi về chức năng không tự kích hoạt tra cứu."
            )
        elif topic == HelpTopic.CONVERSATION:
            answers.append(
                "Bạn có thể trò chuyện đời thường với mình; nội dung đó không được ghi thành tình tiết hoặc căn cứ của hồ sơ."
                if settings.GENERAL_CHAT_ENABLED
                else "Chức năng trò chuyện đời thường hiện đang tạm tắt."
            )
        else:
            answers.append(_ANSWERS[topic])
    return "\n\n".join(answers)
