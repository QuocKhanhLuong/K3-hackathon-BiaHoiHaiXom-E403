const VLearnMockAdapter = (() => {
  const flowLabels = {
    grounded_answer: "Tutor trả lời có căn cứ",
    orchestrator: "Learning Loop Orchestrator",
    simple_end: "Kết thúc lượt",
    clarify: "Hỏi làm rõ",
    understanding_check: "Understanding Check",
    misconception: "Misconception Detection",
    follow_up: "Follow-up Suggestions",
  };

  const session = {
    awaiting: null,
    lastQuestion: "",
  };

  function normalize(value) {
    return value
      .toLowerCase()
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "");
  }

  function citation(page) {
    return `<a class="citation" href="#" data-page="${page}">${page}</a>`;
  }

  function detectIntent(question) {
    const text = normalize(question);
    const wordCount = text.split(/\s+/).filter(Boolean).length;

    if (session.awaiting === "clarification_choice") return "clarification_choice_answered";
    if (session.awaiting === "clarification_text") return "clarification_text_answered";
    if (session.awaiting === "understanding_check") return "check_answered";
    if (wordCount <= 3 || /^(giai thich|noi ro|cai nay|phan nay)$/.test(text)) return "missing_info";
    if (text.includes("quiz") || text.includes("kiem tra") || text.includes("test")) return "needs_check";
    if (text.includes("sai") || text.includes("khong hieu") || text.includes("khong biet")) return "misconception";
    if (text.includes("vi du") || text.includes("khac") || text.includes("tai sao") || text.includes("lien he")) return "deep_dive";
    if (text.includes("tom tat") || text.includes("la gi") || text.includes("slide")) return "simple";
    return "deep_dive";
  }

  function makeTurn(question, context = {}) {
    const intent = detectIntent(question);
    session.lastQuestion = question;

    if (intent === "missing_info") {
      const text = normalize(question);
      const shouldUseChoice = text.includes("cai nay") || text.includes("phan nay") || text.includes("doan nay") || text.includes("slide");

      if (!shouldUseChoice) {
        session.awaiting = "clarification_text";
        return {
          route: "Thiếu thông tin → Học viên nhập thêm",
          steps: ["grounded_answer", "orchestrator", "clarify"],
          awaitingInput: true,
          inputPlaceholder: "Nhập chủ đề, đoạn slide, hoặc mục bạn muốn làm rõ...",
          answer: `
            <p>Mình cần thêm ngữ cảnh trước khi trả lời, vì câu hỏi hiện tại còn quá ngắn.</p>
            <p>Bạn hãy nhập thêm vào ô chat: bạn muốn hỏi về khái niệm nào, slide nào, hoặc đoạn nội dung nào?</p>
          `,
          followUps: [],
        };
      }

      session.awaiting = "clarification_choice";
      return {
        route: "Thiếu thông tin → Multiple choice",
        steps: ["grounded_answer", "orchestrator", "clarify"],
        answer: `
          <p>Mình cần làm rõ mục tiêu trước khi trả lời phần bạn đang xem.</p>
          <p>Bạn muốn tutor xử lý theo hướng nào?</p>
        `,
        followUps: [
          { icon: "1", label: "Tóm tắt đoạn đang chọn", type: "question" },
          { icon: "2", label: "Giải thích thuật ngữ chính", type: "question" },
          { icon: "3", label: "Cho ví dụ dễ hiểu hơn", type: "question" },
        ],
      };
    }

    if (intent === "clarification_choice_answered" || intent === "clarification_text_answered") {
      session.awaiting = "understanding_check";
      const isOpenInput = intent === "clarification_text_answered";
      return {
        route: isOpenInput ? "Học viên nhập thêm → Understanding Check" : "Multiple choice → Understanding Check",
        steps: ["grounded_answer", "orchestrator", "clarify", "understanding_check"],
        answer: `
          <p>Rõ rồi. ${isOpenInput ? "Mình đã dùng phần bạn vừa nhập làm ngữ cảnh bổ sung." : "Mình sẽ xử lý theo lựa chọn bạn vừa bấm."}</p>
          <p>Với đoạn trên slide ${context.currentSlide || 1}, ý chính là: tutor cần dựa vào nội dung bài học trước, sau đó mới quyết định nên trả lời ngắn, hỏi làm rõ, kiểm tra hiểu hay gợi ý đào sâu.</p>
          <p>Kiểm tra nhanh: nếu học viên hỏi quá mơ hồ như “giải thích cái này”, bước tiếp theo hợp lý nhất là gì?</p>
        `,
        followUps: [
          {
            icon: "A",
            label: "Hỏi làm rõ",
            type: "quiz-option",
            correct: true,
            feedback: "Đúng. Khi câu hỏi quá mơ hồ, tutor cần hỏi làm rõ trước khi trả lời.",
          },
          {
            icon: "B",
            label: "Trả lời luôn",
            type: "quiz-option",
            correct: false,
            feedback: "Chưa đúng. Trả lời luôn khi thiếu ngữ cảnh dễ khiến tutor đoán sai ý học viên.",
          },
        ],
      };
    }

    if (intent === "needs_check") {
      session.awaiting = "understanding_check";
      return {
        route: "Cần kiểm tra hiểu",
        steps: ["grounded_answer", "orchestrator", "understanding_check"],
        answer: `
          <p>Mình tạo một understanding check ngắn:</p>
          <p><strong>Câu hỏi:</strong> Ứng dụng nào của NLP giúp rút gọn nội dung dài thành các ý chính?</p>
        `,
        followUps: [
          {
            icon: "A",
            label: "Text Summarization",
            type: "quiz-option",
            correct: true,
            feedback: "Đúng. Text Summarization dùng để rút gọn nội dung dài thành các ý chính.",
          },
          {
            icon: "B",
            label: "Machine Translation",
            type: "quiz-option",
            correct: false,
            feedback: "Chưa đúng. Machine Translation là dịch máy, mục tiêu chính là chuyển văn bản giữa các ngôn ngữ.",
          },
          {
            icon: "C",
            label: "Information Extraction",
            type: "quiz-option",
            correct: false,
            feedback: "Chưa đúng. Information Extraction dùng để lấy thực thể, quan hệ hoặc dữ kiện cụ thể, không phải tóm tắt toàn văn.",
          },
        ],
      };
    }

    if (intent === "check_answered") {
      const text = normalize(question);
      const isWrong = text.includes("translation") || text.includes("tra loi luon") || text.includes("b") || text.includes("sai");
      session.awaiting = isWrong ? "understanding_check" : null;

      if (isWrong) {
        return {
          route: "Sai → Misconception Detection",
          steps: ["understanding_check", "misconception", "understanding_check"],
          answer: `
            <p>Chưa đúng lắm. Đây là nhầm lẫn phổ biến: <strong>Machine Translation</strong> dùng để chuyển ngôn ngữ, còn <strong>Text Summarization</strong> dùng để rút gọn nội dung.</p>
            <p>Thử lại bằng ví dụ mới: nếu bạn có transcript 5 trang và muốn lấy 5 ý chính, đó là ứng dụng nào?</p>
          `,
          followUps: [
            {
              icon: "A",
              label: "Text Summarization",
              type: "quiz-option",
              correct: true,
              feedback: "Đúng. Bài toán yêu cầu rút gọn transcript thành ý chính nên là Text Summarization.",
            },
            {
              icon: "B",
              label: "Information Extraction",
              type: "quiz-option",
              correct: false,
              feedback: "Chưa đúng. Information Extraction sẽ phù hợp hơn nếu bạn cần lấy tên người, mốc thời gian, thuật ngữ hoặc quan hệ cụ thể.",
            },
          ],
        };
      }

      return {
        route: "Đúng → Follow-up Suggestions",
        steps: ["understanding_check", "follow_up", "simple_end"],
        answer: `
          <p>Đúng rồi. <strong>Text Summarization</strong> là ứng dụng dùng để rút gọn nội dung dài thành các ý chính.</p>
          <p>Bạn có thể đi tiếp bằng một ví dụ thực tế hoặc quay lại slide liên quan. ${citation(2)}</p>
        `,
        followUps: [
          { icon: "↗", label: "Nhảy tới slide 2", type: "goto", page: 2 },
          { icon: "◎", label: "Cho ví dụ thực tế", type: "question" },
        ],
      };
    }

    if (intent === "misconception") {
      session.awaiting = "understanding_check";
      return {
        route: "Hiểu sai → Check lại",
        steps: ["grounded_answer", "orchestrator", "misconception", "understanding_check"],
        answer: `
          <p>Mình sẽ sửa lại điểm dễ nhầm: LLM không “tra cứu đáp án cố định” theo kiểu bảng luật. Nó dự đoán token tiếp theo dựa trên ngữ cảnh, dữ liệu đã học và phần tài liệu được đưa vào. ${citation(5)}</p>
          <p>Check lại bằng ví dụ mới: khi tutor cần trả lời bám slide, thành phần nào giúp câu trả lời có căn cứ?</p>
        `,
        followUps: [
          {
            icon: "A",
            label: "Citation/Retrieval",
            type: "quiz-option",
            correct: true,
            feedback: "Đúng. Citation/Retrieval giúp câu trả lời bám nguồn trong slide hoặc tài liệu học.",
          },
          {
            icon: "B",
            label: "Chỉ random text",
            type: "quiz-option",
            correct: false,
            feedback: "Chưa đúng. Random text không có grounding nên rất dễ sai hoặc không liên quan đến slide.",
          },
        ],
      };
    }

    if (intent === "simple") {
      session.awaiting = null;
      return {
        route: "Câu hỏi đơn giản",
        steps: ["grounded_answer", "orchestrator", "simple_end"],
        answer: `
          <p>Dưới đây là câu trả lời ngắn, bám theo slide hiện tại:</p>
          <p><strong>NLP</strong> là nhóm kỹ thuật giúp máy xử lý ngôn ngữ tự nhiên: hỏi đáp, tóm tắt, dịch máy, trích xuất thông tin và phân tích cảm xúc. ${citation(2)}</p>
          <div class="hint">Lượt này đủ thông tin nên adapter kết thúc lượt, nhưng bạn vẫn có thể hỏi tiếp ở ô nhập.</div>
        `,
        followUps: [],
      };
    }

    session.awaiting = null;
    return {
      route: "Có thể đào sâu",
      steps: ["grounded_answer", "orchestrator", "follow_up"],
      answer: `
        <p>Câu hỏi này có thể đào sâu. Mình trả lời trước phần nền:</p>
        <p>Trong workflow tutor, câu trả lời đầu tiên cần có căn cứ từ slide hoặc đoạn học viên chọn. Sau đó orchestrator quyết định bước tiếp: kết thúc lượt, hỏi làm rõ, kiểm tra hiểu, sửa hiểu sai, hoặc gợi ý follow-up. ${citation(5)}</p>
      `,
      followUps: [
        { icon: "?", label: "Cho mình một understanding check", type: "question" },
        { icon: "💬", label: "Syntax và Semantics khác nhau thế nào?", type: "question" },
        { icon: "◎", label: "Ví dụ thực tế của Machine Translation?", type: "question" },
        { icon: "▤", label: "Tóm tắt slide này ngắn gọn", type: "question" },
      ],
    };
  }

  function getInitialTurn() {
    session.awaiting = null;
    return {
      route: "Có thể đào sâu",
      steps: ["grounded_answer", "orchestrator", "follow_up"],
      answer: `
        <p>Dưới đây là các điểm chính từ slide này:</p>
        <p><strong>4. Các ứng dụng tiêu biểu của NLP</strong> ${citation(2)}</p>
        <ul>
          <li><strong>Dịch máy:</strong> chuyển đổi văn bản giữa các ngôn ngữ.</li>
          <li><strong>Hỏi đáp tự động:</strong> trả lời dựa trên tài liệu hoặc kho tri thức. ${citation(3)}</li>
          <li><strong>Tóm tắt văn bản:</strong> rút gọn nội dung chính.</li>
          <li><strong>Trích xuất thông tin:</strong> lấy ra thực thể, quan hệ hoặc dữ kiện. ${citation(4)}</li>
        </ul>
        <div class="hint">Chạm vào số trích dẫn [n] để nhảy đến slide tương ứng.</div>
      `,
      followUps: [
        { icon: "💬", label: "Syntax và Semantics khác nhau thế nào?", type: "question" },
        { icon: "▤", label: "Tóm tắt slide này ngắn gọn", type: "question" },
        { icon: "?", label: "Cho mình 3 câu quiz", type: "question" },
        { icon: "◎", label: "Ví dụ thực tế của Machine Translation?", type: "question" },
      ],
    };
  }

  return {
    flowLabels,
    getInitialTurn,
    makeTurn,
    resolveInlineCheck() {
      session.awaiting = null;
    },
  };
})();
