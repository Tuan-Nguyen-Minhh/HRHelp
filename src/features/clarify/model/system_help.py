"""Approved product Q&A. Topics are selected by the existing semantic router."""

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
    MINUTES_START = "minutes_getting_started"
    MINUTES_INPUTS = "minutes_required_information"
    ROLES = "roles"
    RETURN = "return_process"
    SOURCES = "sources"
    RELIABILITY = "reliability"
    PRIVACY = "privacy"
    CONVERSATION = "conversation_scope"
    NO_MATCH = "no_matching_answer"


NO_HELP_ANSWER = "Tôi tạm thời chưa thể trả lời cho bạn, bạn có thể hỏi kỹ hơn hoặc hỏi câu khác."


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
    HelpTopic.NO_MATCH: NO_HELP_ANSWER,
    HelpTopic.IDENTITY: "Mình là trợ lý AI trong HR Help, hỗ trợ bạn xử lý hồ sơ kỷ luật lao động. Mình không phải người có thẩm quyền ra quyết định.",
    HelpTopic.CAPABILITIES: "Mình có thể giúp làm rõ và xác nhận tình tiết, xem lại thông tin hồ sơ, tra căn cứ nội bộ, chuẩn bị biên bản và phiếu pháp chế để bạn kiểm tra. Việc gửi, xét duyệt và ban hành vẫn theo quyền và điều kiện của hồ sơ.",
    HelpTopic.AUTHORITY: "Mình có thể hỗ trợ phân tích và chuẩn bị nội dung, nhưng không quyết định thay bạn, tự phê duyệt, ký hay bỏ qua bước xét duyệt. Quyết định chính thức do người có thẩm quyền thực hiện tại chức năng tương ứng trong hệ thống.",
    HelpTopic.START: "Bạn có thể tạo hoặc mở hồ sơ được phép truy cập, cung cấp thông tin sự việc rồi kiểm tra và xác nhận tình tiết. Khi cần, hãy yêu cầu lập biên bản; hệ thống sẽ hỏi thêm thông tin còn thiếu.",
    HelpTopic.WORKFLOW: "Luồng chính gồm thu thập và xác nhận tình tiết → đối chiếu căn cứ, chuẩn bị đánh giá/biên bản → HR kiểm tra bản nháp → chuyển xét duyệt theo luồng được hỗ trợ → người có thẩm quyền quyết định. Chat không tự thay thế các bước xét duyệt.",
    HelpTopic.MINUTES: "HR có thể xem, sửa và xác nhận bản nháp biên bản, rồi xuất Word hoặc chuẩn bị gửi xét duyệt khi hồ sơ đủ điều kiện. Nếu chưa đủ thông tin, hệ thống sẽ nêu phần cần bổ sung; mình không tự xác nhận thay HR.",
    HelpTopic.MINUTES_START: (
        "Để tạo biên bản trên HR Help, bạn làm theo các bước sau bằng tài khoản HR:\n\n"
        "1. Bấm Tạo hồ sơ ở phía trên màn hình. Nếu đã có hồ sơ, vào Hồ sơ HR và mở hồ sơ cần xử lý.\n"
        "2. Với hồ sơ mới, nhập thông tin nhân viên, ngày xảy ra vụ việc và mô tả, rồi chọn Tạo hồ sơ để vào hội thoại của hồ sơ.\n"
        "3. Trong hội thoại của hồ sơ, gửi: “Hãy lập biên bản vụ việc này cho tôi.”\n"
        "4. Trả lời các câu hỏi bổ sung của trợ lý; vào Tình tiết vi phạm để kiểm tra, sửa và xác nhận thông tin cần thiết.\n"
        "5. Khi đủ thông tin, mở Đánh giá và biên bản để xem bản nháp. Bạn có thể sửa, Lưu nháp, Xác nhận biên bản và Xuất Word theo trạng thái hồ sơ.\n\n"
        "Bạn có thể hỏi hướng dẫn trong chat nổi; để lập biên bản, hãy dùng hội thoại của hồ sơ. Câu hỏi hướng dẫn này chưa tạo hay gửi biên bản."
    ),
    HelpTopic.MINUTES_INPUTS: (
        "Bạn nên chuẩn bị các thông tin sau để trợ lý hỗ trợ lập biên bản:\n\n"
        "• Hồ sơ và nhân viên: mã hồ sơ, họ tên, mã nhân viên; phòng ban/chức danh nếu có.\n"
        "• Vụ việc: ngày, giờ, địa điểm, diễn biến cụ thể và hành vi được ghi nhận.\n"
        "• Tài liệu liên quan nếu có: bảng chấm công, email, hình ảnh, lời giải trình hoặc thông tin người chứng kiến.\n"
        "• Những nội dung đã xác minh và những điểm còn chưa rõ.\n\n"
        "Khi mở hồ sơ, thông tin cơ bản gồm mã hồ sơ, họ tên/mã nhân viên, ngày xảy ra và mô tả vụ việc. "
        "Phần cần bổ sung để lập biên bản phụ thuộc từng tình huống; trợ lý sẽ hỏi trong hội thoại hồ sơ. "
        "Nếu chưa biết thông tin nào, bạn có thể nói rõ là chưa có, không cần tự điền phỏng đoán."
    ),
    HelpTopic.ROLES: "HR chuẩn bị hồ sơ và kiểm tra biên bản; pháp chế xem xét căn cứ và gửi kết luận; quản lý thực hiện xét duyệt cuối theo quyền. Hệ thống còn có vai trò người ký và quản trị. Các thao tác thực tế phụ thuộc quyền tài khoản và trạng thái hồ sơ.",
    HelpTopic.RETURN: "Khi hồ sơ bị trả lại, HR xem lý do của pháp chế hoặc quản lý, mở bản nháp để sửa, kiểm tra và xác nhận lại trước khi gửi tiếp. Việc hỏi hướng dẫn ở đây không tự sửa hoặc gửi hồ sơ.",
    HelpTopic.RELIABILITY: "Mình có thể hiểu sai hoặc thiếu thông tin, nên không thể cam kết chính xác 100%. Bạn cần đối chiếu nội dung với hồ sơ và nguồn trích dẫn; AI không thay thế trách nhiệm quyết định của người có thẩm quyền.",
    HelpTopic.PRIVACY: "Hệ thống có kiểm tra quyền truy cập hồ sơ và lưu hội thoại phục vụ xử lý. Nội dung cần thiết có thể được gửi tới nhà cung cấp model đang cấu hình. Mình không thể hứa bảo mật tuyệt đối hoặc không lưu dữ liệu; bạn nên tránh gửi mật khẩu và thông tin nhạy cảm không cần thiết.",
}


_TOPIC_SUMMARIES = {
    HelpTopic.IDENTITY: "Giới thiệu trợ lý HR Help.",
    HelpTopic.CAPABILITIES: "Các chức năng được hỗ trợ.",
    HelpTopic.AUTHORITY: "Giới hạn quyền của AI và việc xét duyệt/ký.",
    HelpTopic.START: "Bắt đầu tạo hoặc mở hồ sơ.",
    HelpTopic.WORKFLOW: "Luồng tổng quát từ hồ sơ đến xét duyệt.",
    HelpTopic.MINUTES_START: "Các bước và vị trí thao tác để tạo biên bản.",
    HelpTopic.MINUTES_INPUTS: "Thông tin nên chuẩn bị/cung cấp trước khi lập biên bản.",
    HelpTopic.MINUTES: "Xem, sửa, xác nhận và xuất bản nháp biên bản.",
    HelpTopic.ROLES: "Vai trò HR, pháp chế, quản lý, người ký và quản trị.",
    HelpTopic.RETURN: "Sửa và gửi lại hồ sơ bị trả về.",
    HelpTopic.SOURCES: "Nguồn nội bộ/công khai và trạng thái cấu hình tra cứu.",
    HelpTopic.RELIABILITY: "Giới hạn độ tin cậy và kiểm tra câu trả lời.",
    HelpTopic.PRIVACY: "Quyền truy cập, lưu và xử lý dữ liệu.",
    HelpTopic.CONVERSATION: "Phạm vi trò chuyện đời thường.",
    HelpTopic.NO_MATCH: "Không có nội dung Q&A phù hợp với câu hỏi.",
}


def help_topic_catalog() -> str:
    """Describe answer scopes briefly; do not prescribe how users must phrase questions."""
    return "Q&A TOPICS\n" + "\n".join(f"{topic.value}: {summary}" for topic, summary in _TOPIC_SUMMARIES.items())


def resolve_help_topics(question: str, topics: list[HelpTopic] | None = None) -> list[HelpTopic]:
    selected = list(dict.fromkeys(topics or []))
    return selected[:3]


def answer_system_help(question: str, topics: list[HelpTopic] | None = None) -> str:
    if not settings.SYSTEM_HELP_ENABLED:
        return "Chức năng hỏi đáp về hệ thống hiện đang tạm tắt."
    selected = resolve_help_topics(question, topics)
    # An explicit empty selection from the semantic router means no answer was found.
    # Legacy direct calls without topic hints may still resolve a catalog topic locally.
    if not selected and topics is None:
        folded = fold_text(question)
        selected = [topic for topic, pattern in _PATTERNS.items() if re.search(r"\b(?:" + pattern + r")\b", folded)]
    if not selected or HelpTopic.NO_MATCH in selected:
        return NO_HELP_ANSWER
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
            answer = _ANSWERS.get(topic)
            if not answer:
                return NO_HELP_ANSWER
            answers.append(answer)
    return "\n\n".join(answers) or NO_HELP_ANSWER
