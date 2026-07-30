/**
 * VLearn Adaptive Tutor Frontend Engine
 * Implements Updated Workflow Logic
 */

document.addEventListener('DOMContentLoaded', () => {
  // App State
  let currentPage = 1;
  let currentDeckId = 'd1';
  let totalPages = 5;
  let slidesData = [];
  let selectedTextOnSlide = "";
  let chatHistory = [];
  let currentThreadId = null;

  // DOM Elements
  const leftPane = document.getElementById('leftPane');
  const rightPane = document.getElementById('rightPane');
  const resizer = document.getElementById('resizer');
  
  const slideTitle = document.getElementById('slideTitle');
  const slideSubtitle = document.getElementById('slideSubtitle');
  const slideBody = document.getElementById('slideBody');
  const slideFileRef = document.getElementById('slideFileRef');
  const currentPageNum = document.getElementById('currentPageNum');
  const totalPagesNum = document.getElementById('totalPagesNum');
  const tutorSlideBadge = document.getElementById('tutorSlideBadge');
  const selectionTooltip = document.getElementById('selectionTooltip');
  const slideCard = document.getElementById('slideCard');
  const bookStage = document.querySelector('.book-stage');
  const originalSlideImage = document.getElementById('originalSlideImage');
  const slideImageLoading = document.getElementById('slideImageLoading');
  const zoomOutBtn = document.getElementById('zoomOutBtn');
  const zoomInBtn = document.getElementById('zoomInBtn');
  const zoomVal = document.getElementById('zoomVal');
  const annotationCanvas = document.getElementById('annotationCanvas');
  const annotationCtx = annotationCanvas.getContext('2d');
  const readToolBtn = document.getElementById('readToolBtn');
  const penToolBtn = document.getElementById('penToolBtn');
  const highlightToolBtn = document.getElementById('highlightToolBtn');
  const eraserToolBtn = document.getElementById('eraserToolBtn');
  const penColorPopover = document.getElementById('penColorPopover');
  const highlightColorPopover = document.getElementById('highlightColorPopover');
  const penColorDot = document.getElementById('penColorDot');
  const highlightColorDot = document.getElementById('highlightColorDot');

  let activeTool = 'read';
  let penColor = '#0878d1';
  let highlightColor = '#ffe066';
  let isDrawing = false;
  let lastPoint = null;
  let annotationResizeTimer = null;
  let currentZoom = 90;
  const minZoom = 50;
  const maxZoom = 180;
  const zoomStep = 10;
  const slideBaseWidth = 640;

  const notePageNum = document.getElementById('notePageNum');
  const pageNoteBadge = document.getElementById('pageNoteBadge');
  const noteTextarea = document.getElementById('noteTextarea');
  const noteSaveStatus = document.getElementById('noteSaveStatus');
  const notePanel = document.getElementById('notePanel');
  const toggleNoteBtn = document.getElementById('toggleNoteBtn');

  const prevPageBtn = document.getElementById('prevPageBtn');
  const nextPageBtn = document.getElementById('nextPageBtn');

  const chatMessages = document.getElementById('chatMessages');
  const chatInput = document.getElementById('chatInput');
  const sendBtn = document.getElementById('sendBtn');
  const activeNodeBadge = document.getElementById('activeNodeBadge');

  const themeToggleBtn = document.getElementById('themeToggleBtn');
  const wfModal = document.getElementById('wfModal');
  const openWfModalBtn = document.getElementById('openWfModalBtn');
  const closeWfModalBtn = document.getElementById('closeWfModalBtn');

  // 1. Fetch & Render Slides
  async function loadSlides() {
    try {
      const res = await fetch('/api/slides');
      const data = await res.json();
      slidesData = data.slides;
      totalPages = data.total_pages;
      totalPagesNum.textContent = totalPages;
      renderSlide(currentPage);
    } catch (err) {
      console.warn('Backend not available, using fallback slides:', err);
      slidesData = [
        {
          page: 1,
          title: "AI Product Thinking & Requirements",
          subtitle: "AICB-P1 · Ngày 5 · Build agent xong, nhưng sản phẩm cho ai?",
          content: "<p><b>Tên Giảng Viên:</b> VinUniversity Phase 1 Tuần 1 2026.</p><p>Giới thiệu tổng quan về tư duy thiết kế sản phẩm AI cho người dùng thật. Không dừng lại ở prototype kỹ thuật mà tập trung vào giá trị mang lại cho end-user.</p>",
          code: "Lecture_material_ms204v3b_r9mo78"
        },
        {
          page: 2,
          title: "HÃY SUY NGHĨ: Bạn đã build xong Agent chưa?",
          subtitle: "Vấn đề của người dùng vs Prototype kỹ thuật",
          content: "<p>Nhiều đội nhóm tập trung 90% thời gian gọi API và chỉnh prompt, nhưng quên mất người dùng gặp vấn đề gì.</p><p>Bài toán sản phẩm AI đòi hỏi bằng chứng thực tế từ khảo sát hoặc data mining chứ không phải cảm tính.</p>",
          code: "Lecture_material_ms204v3b_r9mo78"
        },
        {
          page: 3,
          title: "Khung Xác định Bài toán & Chỗ khó (Taxonomy)",
          subtitle: "4 Lớp Chỗ Khó Cần Thiết Kế Cụ Thể",
          content: "<p>Duyệt qua 4 lớp chỗ khó theo Taxonomy:</p><ul><li><b>① Nguồn sự thật (Grounding):</b> Chỗ nào AI bịa được?</li><li><b>② Mơ mơ / Thiếu thông tin:</b> Input không đủ chắc thì hỏi lại hay đoán?</li><li><b>③ Ngoài thẩm quyền:</b> User đòi thứ không cho phép.</li><li><b>④ Đặc thù Domain:</b> Sai cái gì thì mất điểm/mất niềm tin?</li></ul>",
          code: "Lecture_material_ms204v3b_r9mo78"
        },
        {
          page: 4,
          title: "Function Calling & Agent Tools Contract",
          subtitle: "Cho Model Một \"Hợp Đồng\" Rõ Ràng",
          content: "<p>Text-based ReAct vs Structured Function Calling.</p><p>Function Calling cung cấp hợp đồng rõ ràng dạng <b>JSON Schema</b> giúp Agent thực thi hành động chính xác thay vì tự đoán văn bản ngẫu nhiên.</p>",
          code: "Lecture_material_ms204v3b_r9mo78"
        },
        {
          page: 5,
          title: "Quản lý Ngữ cảnh (Context Management)",
          subtitle: "Phân bổ Token Budget Cân Bằng",
          content: "<p>Context bao gồm 5 thành phần chính:</p><ul><li><b>System policy:</b> Định nghĩa vai trò & luật lệ.</li><li><b>History:</b> Lịch sử hội thoại gần đây.</li><li><b>Current input:</b> Yêu cầu của người dùng.</li><li><b>Tools schemas:</b> Định nghĩa công cụ.</li><li><b>Output buffer:</b> Khoảng trống sinh kết quả.</li></ul>",
          code: "Lecture_material_ms204v3b_r9mo78"
        }
      ];
      totalPages = slidesData.length;
      totalPagesNum.textContent = totalPages;
      renderSlide(currentPage);
    }
  }

  function renderSlide(pageNum) {
    const slide = slidesData.find(s => s.page === pageNum && (s.deck_id || 'd1') === currentDeckId) || slidesData[0];
    currentDeckId = slide.deck_id || currentDeckId;
    slideTitle.textContent = slide.title;
    slideSubtitle.textContent = slide.subtitle || "";
    slideBody.innerHTML = slide.content;
    slideFileRef.textContent = slide.code || "day05-ai-product-thinking-requirements.pdf";
    slideCard.classList.add('pdf-render-mode', 'slide-image-is-loading');
    originalSlideImage.alt = `Slide trang ${pageNum}: ${slide.title || ''}`;
    originalSlideImage.onload = () => {
      slideCard.classList.remove('slide-image-is-loading', 'slide-image-error');
      window.requestAnimationFrame(() => resizeAnnotationCanvas(true));
    };
    originalSlideImage.onerror = () => {
      slideCard.classList.remove('slide-image-is-loading', 'pdf-render-mode');
      slideCard.classList.add('slide-image-error');
      slideImageLoading.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i><span>Không thể tải ảnh slide gốc. Đang hiển thị bản nội dung dự phòng.</span>';
      window.requestAnimationFrame(() => resizeAnnotationCanvas(true));
    };
    originalSlideImage.src = `/api/slides/${pageNum}/render?deck_id=${encodeURIComponent(currentDeckId)}`;

    currentPageNum.textContent = pageNum;
    tutorSlideBadge.textContent = pageNum;
    notePageNum.textContent = pageNum;
    pageNoteBadge.textContent = `Trang ${pageNum} · 1 note`;

    const savedNote = localStorage.getItem(`vlearn_note_page_${pageNum}`) || "";
    noteTextarea.value = savedNote;
    if (originalSlideImage.complete) window.requestAnimationFrame(() => resizeAnnotationCanvas(true));
  }

  function applyZoom(nextZoom) {
    currentZoom = Math.min(maxZoom, Math.max(minZoom, nextZoom));
    zoomVal.textContent = `${currentZoom}%`;
    bookStage.style.width = `${Math.round(slideBaseWidth * currentZoom / 100)}px`;
    zoomOutBtn.disabled = currentZoom <= minZoom;
    zoomInBtn.disabled = currentZoom >= maxZoom;
    zoomOutBtn.setAttribute('aria-label', `Thu nhỏ slide, hiện tại ${currentZoom}%`);
    zoomInBtn.setAttribute('aria-label', `Phóng lớn slide, hiện tại ${currentZoom}%`);

    clearTimeout(annotationResizeTimer);
    annotationResizeTimer = setTimeout(() => resizeAnnotationCanvas(false), 180);
  }

  zoomOutBtn.addEventListener('click', () => applyZoom(currentZoom - zoomStep));
  zoomInBtn.addEventListener('click', () => applyZoom(currentZoom + zoomStep));

  // Slide annotation tools: pen and translucent highlighter
  const penColors = ['#0878d1', '#102b46', '#ef4444', '#16a34a', '#8b5cf6'];
  const highlightColors = ['#ffe066', '#78e6b0', '#75d5ff', '#ff9fc5', '#c4b5fd'];

  function buildColorPopover(popover, colors, tool) {
    colors.forEach(color => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'color-swatch';
      button.style.backgroundColor = color;
      button.setAttribute('aria-label', `Chọn màu ${color}`);
      button.addEventListener('click', (event) => {
        event.stopPropagation();
        if (tool === 'pen') {
          penColor = color;
          penColorDot.style.background = color;
        } else {
          highlightColor = color;
          highlightColorDot.style.background = color;
        }
        setActiveTool(tool);
        closeColorPopovers();
      });
      popover.appendChild(button);
    });
  }

  function closeColorPopovers() {
    penColorPopover.classList.remove('visible');
    highlightColorPopover.classList.remove('visible');
  }

  function setActiveTool(tool) {
    activeTool = tool;
    [readToolBtn, penToolBtn, highlightToolBtn, eraserToolBtn].forEach(btn => btn.classList.remove('active'));
    const activeButton = tool === 'pen'
      ? penToolBtn
      : tool === 'highlight'
        ? highlightToolBtn
        : tool === 'eraser'
          ? eraserToolBtn
          : readToolBtn;
    activeButton.classList.add('active');
    annotationCanvas.classList.toggle('drawing-enabled', tool !== 'read');
    slideCard.classList.toggle('annotation-mode', tool !== 'read');
    selectionTooltip.style.display = 'none';
    window.getSelection()?.removeAllRanges();
  }

  function resizeAnnotationCanvas(restore = false) {
    const rect = slideCard.getBoundingClientRect();
    if (!rect.width || !rect.height) return;
    const savedImage = annotationCanvas.width && annotationCanvas.height
      ? annotationCanvas.toDataURL()
      : null;
    const ratio = Math.min(window.devicePixelRatio || 1, 2);
    annotationCanvas.width = Math.round(rect.width * ratio);
    annotationCanvas.height = Math.round(rect.height * ratio);
    annotationCanvas.style.width = `${rect.width}px`;
    annotationCanvas.style.height = `${rect.height}px`;
    annotationCtx.setTransform(ratio, 0, 0, ratio, 0, 0);
    annotationCtx.lineCap = 'round';
    annotationCtx.lineJoin = 'round';

    if (restore) {
      loadAnnotation(currentPage);
    } else if (savedImage) {
      const image = new Image();
      image.onload = () => annotationCtx.drawImage(image, 0, 0, rect.width, rect.height);
      image.src = savedImage;
    }
  }

  function loadAnnotation(page) {
    annotationCtx.clearRect(0, 0, annotationCanvas.width, annotationCanvas.height);
    const saved = localStorage.getItem(`vlearn_annotation_page_${page}`);
    if (!saved) return;
    const image = new Image();
    image.onload = () => {
      const rect = slideCard.getBoundingClientRect();
      annotationCtx.drawImage(image, 0, 0, rect.width, rect.height);
    };
    image.src = saved;
  }

  function saveAnnotation() {
    localStorage.setItem(`vlearn_annotation_page_${currentPage}`, annotationCanvas.toDataURL('image/png'));
  }

  function canvasPoint(event) {
    const rect = annotationCanvas.getBoundingClientRect();
    return { x: event.clientX - rect.left, y: event.clientY - rect.top };
  }

  function startDrawing(event) {
    if (activeTool === 'read') return;
    event.preventDefault();
    isDrawing = true;
    lastPoint = canvasPoint(event);
    annotationCanvas.setPointerCapture(event.pointerId);
  }

  function draw(event) {
    if (!isDrawing || activeTool === 'read') return;
    event.preventDefault();
    const point = canvasPoint(event);
    annotationCtx.beginPath();
    annotationCtx.moveTo(lastPoint.x, lastPoint.y);
    annotationCtx.lineTo(point.x, point.y);
    const isEraser = activeTool === 'eraser';
    annotationCtx.strokeStyle = isEraser ? '#000000' : activeTool === 'pen' ? penColor : highlightColor;
    annotationCtx.globalAlpha = activeTool === 'highlight' ? 0.32 : 1;
    annotationCtx.globalCompositeOperation = isEraser ? 'destination-out' : 'source-over';
    annotationCtx.lineWidth = isEraser ? 28 : activeTool === 'pen' ? 3 : 18;
    annotationCtx.stroke();
    annotationCtx.globalAlpha = 1;
    annotationCtx.globalCompositeOperation = 'source-over';
    lastPoint = point;
  }

  function stopDrawing(event) {
    if (!isDrawing) return;
    isDrawing = false;
    lastPoint = null;
    if (annotationCanvas.hasPointerCapture(event.pointerId)) annotationCanvas.releasePointerCapture(event.pointerId);
    saveAnnotation();
  }

  buildColorPopover(penColorPopover, penColors, 'pen');
  buildColorPopover(highlightColorPopover, highlightColors, 'highlight');
  penColorDot.style.background = penColor;
  highlightColorDot.style.background = highlightColor;

  readToolBtn.addEventListener('click', () => { setActiveTool('read'); closeColorPopovers(); });
  penToolBtn.addEventListener('click', (event) => {
    event.stopPropagation();
    setActiveTool('pen');
    highlightColorPopover.classList.remove('visible');
    penColorPopover.classList.toggle('visible');
  });
  highlightToolBtn.addEventListener('click', (event) => {
    event.stopPropagation();
    setActiveTool('highlight');
    penColorPopover.classList.remove('visible');
    highlightColorPopover.classList.toggle('visible');
  });
  eraserToolBtn.addEventListener('click', () => {
    setActiveTool('eraser');
    closeColorPopovers();
  });
  document.addEventListener('click', closeColorPopovers);
  annotationCanvas.addEventListener('pointerdown', startDrawing);
  annotationCanvas.addEventListener('pointermove', draw);
  annotationCanvas.addEventListener('pointerup', stopDrawing);
  annotationCanvas.addEventListener('pointercancel', stopDrawing);
  window.addEventListener('resize', () => {
    clearTimeout(annotationResizeTimer);
    annotationResizeTimer = setTimeout(() => resizeAnnotationCanvas(false), 120);
  });

  function turnPage(targetPage, direction) {
    const slideCard = document.getElementById('slideCard');
    if (slideCard.classList.contains('is-turning')) return;

    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reduceMotion) {
      currentPage = targetPage;
      renderSlide(currentPage);
      return;
    }

    slideCard.classList.add('is-turning', `turn-${direction}`);
    window.setTimeout(() => {
      currentPage = targetPage;
      renderSlide(currentPage);
      slideCard.classList.add('page-swapped');
    }, 260);

    window.setTimeout(() => {
      slideCard.classList.remove('is-turning', `turn-${direction}`, 'page-swapped');
    }, 620);
  }

  // 2. Note Auto-Save
  noteTextarea.addEventListener('input', () => {
    noteSaveStatus.textContent = "Đang lưu...";
    localStorage.setItem(`vlearn_note_page_${currentPage}`, noteTextarea.value);
    setTimeout(() => {
      noteSaveStatus.textContent = "Đã lưu";
    }, 600);
  });

  toggleNoteBtn.addEventListener('click', () => {
    notePanel.style.display = notePanel.style.display === 'none' ? 'flex' : 'none';
  });

  // 3. Page Navigation
  prevPageBtn.addEventListener('click', () => {
    if (currentPage > 1) {
      turnPage(currentPage - 1, 'backward');
    }
  });

  nextPageBtn.addEventListener('click', () => {
    if (currentPage < totalPages) {
      turnPage(currentPage + 1, 'forward');
    }
  });

  // 4. Slide Text Selection Tooltip
  slideCard.addEventListener('mouseup', (e) => {
    if (activeTool !== 'read') return;
    const sel = window.getSelection();
    const text = sel.toString().trim();
    if (text.length > 3) {
      selectedTextOnSlide = text;
      selectionTooltip.style.top = `${e.offsetY - 35}px`;
      selectionTooltip.style.left = `${e.offsetX + 10}px`;
      selectionTooltip.style.display = 'block';
    } else {
      selectionTooltip.style.display = 'none';
    }
  });

  selectionTooltip.addEventListener('click', () => {
    chatInput.value = `(Trang ${currentPage}, đoạn được chọn: "${selectedTextOnSlide}") Hãy giải thích đoạn này`;
    selectionTooltip.style.display = 'none';
    chatInput.focus();
  });

  // 5. Chat Messaging & Multi-Agent API Engine
  async function sendMessage(textOverride = null) {
    const text = textOverride || chatInput.value.trim();
    if (!text) return;

    appendMessage('student', text);
    if (!textOverride) chatInput.value = '';

    activeNodeBadge.textContent = "⚙️ Đang suy nghĩ...";
    activeNodeBadge.style.background = "#fef08a";
    const thinkingTrace = createThinkingTrace();

    try {
      const data = await requestTutorStream({
        question: text,
        selected_text: selectedTextOnSlide,
        page_number: currentPage,
        deck_id: currentDeckId,
        chat_history: chatHistory,
        thread_id: currentThreadId
      }, thinkingTrace);
      
      if (data.thread_id) currentThreadId = data.thread_id;
      
      activeNodeBadge.textContent = `📍 ${data.orchestrator.title}`;
      activeNodeBadge.style.background = "#dcfce7";
      completeThinkingTrace(thinkingTrace);

      // Render Grounded Answer (contains Deep-dive Expansion if branch == 'followup')
      const hasAnswer = Boolean(data.answer && String(data.answer).trim());
      const answerMessage = hasAnswer ? appendTutorAnswer(data.answer, data.citation_objects || data.citations, data.orchestrator) : null;
      if (answerMessage) attachTraceControl(answerMessage, thinkingTrace);

      // Render Tool Card based on Orchestrator decision
      if (data.tool_data) {
        if (data.orchestrator.branch === 'clarify') {
          renderClarificationCard(data.tool_data);
        } else if (data.orchestrator.branch === 'understanding_check' || data.orchestrator.branch === 'followup') {
          // If branch is 'followup', after Mở rộng tri thức -> points to Understanding Check (Quiz)!
          renderQuizCard(data.tool_data);
        }
      }

      // Only end a non-interactive answer with suggestions. Quiz/clarification
      // branches must wait for the learner's response before deciding next step.
      if (data.default_suggestions && !data.tool_data) {
        renderFollowupChips(data.default_suggestions);
      }

      selectedTextOnSlide = "";
    } catch (err) {
      console.error('API Error:', err);
      failThinkingTrace(thinkingTrace);
      activeNodeBadge.textContent = "⚠️ Không thể xử lý";
      activeNodeBadge.style.background = "#fee2e2";
      const backendMessage = (err && err.message && !/failed to fetch/i.test(err.message))
        ? err.message
        : "Không thể kết nối tới VLearn. Bạn vui lòng kiểm tra backend và thử lại.";
      const fallbackAnswer = appendTutorAnswer(
        backendMessage,
        [],
        { title: "Không thể xử lý" }
      );
      attachTraceControl(fallbackAnswer, thinkingTrace);
    }
  }

  async function requestTutorStream(payload, traceElement) {
    const response = await fetch('/api/tutor/ask/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Accept': 'text/event-stream' },
      body: JSON.stringify(payload)
    });
    if (!response.ok || !response.body) throw new Error(`Streaming API error: ${response.status}`);

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let finalData = null;

    while (true) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
      const events = buffer.split('\n\n');
      buffer = events.pop() || '';

      events.forEach(block => {
        const dataLine = block.split('\n').find(line => line.startsWith('data: '));
        if (!dataLine) return;
        const event = JSON.parse(dataLine.slice(6));
        if (event.type === 'trace') updateThinkingTrace(traceElement, event);
        if (event.type === 'result') finalData = event.data;
        if (event.type === 'error') {
          throw new Error(event.error?.message || event.message || 'Tutor stream failed');
        }
      });
      if (done) break;
    }

    if (!finalData) throw new Error('Tutor stream ended without a result');
    return finalData;
  }

  function createThinkingTrace() {
    const trace = document.createElement('div');
    trace.className = 'thinking-trace';
    trace.innerHTML = `
      <button type="button" class="thinking-trace-toggle" aria-expanded="true">
        <span class="thinking-trace-title"><span class="thinking-pulse"></span> VLearn đang xử lý</span>
        <span class="thinking-trace-meta">0 bước <i class="fa-solid fa-chevron-up"></i></span>
      </button>
      <div class="thinking-trace-body">
        <div class="thinking-trace-intro">Tiến trình công cụ theo thời gian thực</div>
        <div class="thinking-trace-steps"></div>
      </div>
    `;
    chatMessages.appendChild(trace);
    trace.dataset.traceId = `trace-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
    trace.querySelector('.thinking-trace-toggle').addEventListener('click', () => toggleThinkingTrace(trace));
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return trace;
  }

  function updateThinkingTrace(trace, event) {
    const steps = trace.querySelector('.thinking-trace-steps');
    let step = steps.querySelector(`[data-tool="${event.tool}"]`);
    if (!step) {
      step = document.createElement('div');
      step.className = 'thinking-step';
      step.dataset.tool = event.tool;
      step.innerHTML = `
        <span class="thinking-step-icon"><i class="fa-solid fa-circle-notch fa-spin"></i></span>
        <span class="thinking-step-copy"><strong></strong><small></small></span>
        <span class="thinking-step-status">Đang chạy</span>
      `;
      steps.appendChild(step);
    }
    step.querySelector('strong').textContent = event.title;
    step.querySelector('small').textContent = event.detail || '';
    step.classList.toggle('completed', event.status === 'completed');
    if (event.status === 'completed') {
      step.querySelector('.thinking-step-icon').innerHTML = '<i class="fa-solid fa-check"></i>';
      step.querySelector('.thinking-step-status').textContent = 'Xong';
    }
    const count = steps.children.length;
    trace.querySelector('.thinking-trace-meta').childNodes[0].textContent = `${count} bước `;
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  function completeThinkingTrace(trace) {
    trace.classList.add('completed');
    trace.querySelector('.thinking-trace-title').innerHTML = '<i class="fa-solid fa-circle-check"></i> Đã hoàn tất tiến trình';
    window.setTimeout(() => {
      trace.classList.add('collapsed');
      trace.querySelector('.thinking-trace-toggle').setAttribute('aria-expanded', 'false');
      syncTraceControls(trace);
    }, 900);
  }

  function failThinkingTrace(trace) {
    trace.classList.add('failed');
    trace.querySelector('.thinking-trace-title').innerHTML = '<i class="fa-solid fa-circle-exclamation"></i> Không thể tải tiến trình';
  }

  function toggleThinkingTrace(trace, forceExpanded = null) {
    const shouldExpand = forceExpanded === null ? trace.classList.contains('collapsed') : forceExpanded;
    trace.classList.toggle('collapsed', !shouldExpand);
    trace.querySelector('.thinking-trace-toggle').setAttribute('aria-expanded', String(shouldExpand));
    syncTraceControls(trace);
    if (shouldExpand) {
      window.setTimeout(() => trace.scrollIntoView({ behavior: 'smooth', block: 'nearest' }), 80);
    }
  }

  function syncTraceControls(trace) {
    const expanded = !trace.classList.contains('collapsed');
    const stepCount = trace.querySelectorAll('.thinking-step').length;
    document.querySelectorAll(`[data-controls-trace="${trace.dataset.traceId}"]`).forEach(button => {
      button.innerHTML = expanded
        ? '<i class="fa-regular fa-eye-slash"></i> Ẩn tiến trình'
        : `<i class="fa-regular fa-eye"></i> Xem tiến trình (${stepCount} bước)`;
      button.setAttribute('aria-expanded', String(expanded));
    });
  }

  function attachTraceControl(messageElement, trace) {
    const controlRow = document.createElement('div');
    controlRow.className = 'answer-trace-control-row';
    const control = document.createElement('button');
    control.type = 'button';
    control.className = 'answer-trace-toggle';
    control.dataset.controlsTrace = trace.dataset.traceId;
    control.setAttribute('aria-expanded', 'true');
    control.innerHTML = '<i class="fa-regular fa-eye-slash"></i> Ẩn tiến trình';
    control.addEventListener('click', () => toggleThinkingTrace(trace));
    controlRow.appendChild(control);
    messageElement.insertAdjacentElement('beforebegin', controlRow);
    syncTraceControls(trace);
  }

  function appendMessage(role, text) {
    const msgDiv = document.createElement('div');
    msgDiv.className = `msg-bubble msg-${role}`;
    msgDiv.textContent = text;
    chatMessages.appendChild(msgDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  function appendTutorAnswer(text, citations = [], orchestrator = {}) {
    const msgDiv = document.createElement('div');
    msgDiv.className = 'msg-bubble msg-tutor';

    const meta = document.createElement('div');
    meta.style.cssText = 'font-size:11px; color:#64748b; margin-bottom:4px;';
    meta.textContent = `Tutor trả lời · ${orchestrator.title || 'VLearn'}`;
    const body = document.createElement('div');
    body.textContent = String(text || '');
    msgDiv.append(meta, body);
    if (citations && citations.length > 0) citations.forEach(c => {
      const page = parseInt(String(typeof c === 'object' ? c.page_number : c).match(/\d+/)?.[0], 10);
      if (!Number.isFinite(page)) return;
      const button = document.createElement('button');
      button.type = 'button'; button.className = 'citation-tag'; button.dataset.page = String(page);
      button.dataset.deckId = typeof c === 'object' ? (c.deck_id || currentDeckId) : currentDeckId;
      button.title = `Mở slide trang ${page}`; button.textContent = `Trang ${page}`;
      body.append(' ', button);
    });
    chatMessages.appendChild(msgDiv);
    msgDiv.querySelectorAll('.citation-tag').forEach(citation => {
      citation.addEventListener('click', () => {
        const page = parseInt(citation.dataset.page, 10);
        openCitation(page, msgDiv, citation.dataset.deckId || currentDeckId);
      });
    });
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return msgDiv;
  }

  function openCitation(page, messageElement, deckId = currentDeckId) {
    currentDeckId = deckId;
    if (!Number.isFinite(page) || page < 1 || page > totalPages) return;

    if (page !== currentPage) {
      turnPage(page, page > currentPage ? 'forward' : 'backward');
    } else {
      slideCard.classList.remove('citation-focus');
      void slideCard.offsetWidth;
      slideCard.classList.add('citation-focus');
      window.setTimeout(() => slideCard.classList.remove('citation-focus'), 900);
    }

    window.setTimeout(() => slideCard.scrollIntoView({ behavior: 'smooth', block: 'center' }), page === currentPage ? 0 : 320);
    renderCitationPreview(page, messageElement);
  }

  function renderCitationPreview(activePage, messageElement) {
    document.querySelectorAll('.citation-preview').forEach(preview => preview.remove());

    const preview = document.createElement('div');
    preview.className = 'citation-preview';
    preview.innerHTML = `
      <div class="citation-preview-header">
        <div><i class="fa-regular fa-file-lines"></i> <strong>Nguồn slide</strong> · ${slidesData.length} trang</div>
        <button type="button" class="citation-preview-close" aria-label="Đóng xem nhanh">&times;</button>
      </div>
      <div class="citation-preview-scroll">
        ${slidesData.map(slide => `
          <button type="button" class="citation-mini-slide ${slide.page === activePage ? 'active' : ''}" data-page="${slide.page}">
            <span class="citation-mini-page">${slide.page}</span>
            <span class="citation-mini-content">
              <strong>${escapePreviewText(slide.title || `Trang ${slide.page}`)}</strong>
              <span>${escapePreviewText(stripPreviewHtml(slide.content || '')).slice(0, 150)}</span>
            </span>
            <i class="fa-solid fa-arrow-up-right-from-square"></i>
          </button>
        `).join('')}
      </div>
    `;

    messageElement.insertAdjacentElement('afterend', preview);
    preview.querySelector('.citation-preview-close').addEventListener('click', () => preview.remove());
    preview.querySelectorAll('.citation-mini-slide').forEach(item => {
      item.addEventListener('click', () => {
        const targetPage = parseInt(item.dataset.page, 10);
        if (targetPage !== currentPage) turnPage(targetPage, targetPage > currentPage ? 'forward' : 'backward');
        preview.querySelectorAll('.citation-mini-slide').forEach(slide => slide.classList.remove('active'));
        item.classList.add('active');
        window.setTimeout(() => slideCard.scrollIntoView({ behavior: 'smooth', block: 'center' }), 320);
      });
    });

    window.requestAnimationFrame(() => {
      preview.querySelector('.citation-mini-slide.active')?.scrollIntoView({ block: 'nearest' });
    });
    chatMessages.scrollTop = preview.offsetTop - 12;
  }

  function stripPreviewHtml(html) {
    const temporary = document.createElement('div');
    temporary.innerHTML = html;
    return temporary.textContent || temporary.innerText || '';
  }

  function escapePreviewText(text) {
    return String(text)
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#039;');
  }

  // Tool Render 1: Clarification Options
  function renderClarificationCard(clarifyData) {
    const suggestions = Array.isArray(clarifyData.suggested_inputs)
      ? clarifyData.suggested_inputs
      : [];
    const card = document.createElement('div');
    card.className = 'quiz-card';
    card.innerHTML = `
      <div class="quiz-header"><i class="fa-solid fa-circle-question"></i> Hỏi làm rõ</div>
      <div class="quiz-question">${escapePreviewText(clarifyData.clarifying_question || '')}</div>
      <div class="quiz-options">
        ${suggestions.map(opt => `<button class="quiz-opt-btn clarify-opt-btn">${escapePreviewText(opt)}</button>`).join('')}
      </div>
    `;
    chatMessages.appendChild(card);
    chatMessages.scrollTop = chatMessages.scrollHeight;

    card.querySelectorAll('.clarify-opt-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        sendMessage(btn.textContent);
      });
    });
  }

  // Tool Render 2: Interactive Quiz Card
  function renderQuizCard(quizData) {
    const card = document.createElement('div');
    card.className = 'quiz-card';

    const isShortAnswer = (quizData.quiz_type === 'short_answer' || !quizData.options || quizData.options.length === 0);

    if (isShortAnswer) {
      card.innerHTML = `
        <div class="quiz-header"><i class="fa-solid fa-pen-to-square"></i> Understanding Check (Tự luận ngắn) — ${escapePreviewText(quizData.concept || '')}</div>
        <div class="quiz-question">${escapePreviewText(quizData.question || '')}</div>
        <div class="short-answer-wrapper">
          <input type="text" class="short-answer-input" placeholder="Gõ câu trả lời của bạn tại đây...">
          <button class="short-answer-submit-btn"><i class="fa-solid fa-paper-plane"></i> Gửi câu trả lời</button>
        </div>
      `;
      chatMessages.appendChild(card);
      chatMessages.scrollTop = chatMessages.scrollHeight;

      const shortInput = card.querySelector('.short-answer-input');
      const submitBtn = card.querySelector('.short-answer-submit-btn');

      const handleShortSubmit = async () => {
        const userText = shortInput.value.trim();
        if (!userText) return;
        shortInput.disabled = true;
        submitBtn.disabled = true;

        await submitQuizPayload({
          quiz_id: quizData.quiz_id,
          thread_id: currentThreadId,
          quiz_type: "short_answer",
          user_text_answer: userText,
          question_text: quizData.question,
          page_number: currentPage
        }, card);
      };

      submitBtn.addEventListener('click', handleShortSubmit);
      shortInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') handleShortSubmit();
      });

    } else {
      card.innerHTML = `
        <div class="quiz-header"><i class="fa-solid fa-square-check"></i> Understanding Check (Trắc nghiệm) — ${escapePreviewText(quizData.concept || '')}</div>
        <div class="quiz-question">${escapePreviewText(quizData.question || '')}</div>
        <div class="quiz-options">
          ${quizData.options.map((opt, idx) => `<button class="quiz-opt-btn quiz-choice-btn" data-idx="${idx}">${escapePreviewText(opt)}</button>`).join('')}
        </div>
      `;
      chatMessages.appendChild(card);
      chatMessages.scrollTop = chatMessages.scrollHeight;

      card.querySelectorAll('.quiz-choice-btn').forEach(btn => {
        btn.addEventListener('click', async () => {
          const selectedIdx = parseInt(btn.getAttribute('data-idx'));
          await submitQuizPayload({
            quiz_id: quizData.quiz_id,
            thread_id: currentThreadId,
            quiz_type: "multiple_choice",
            selected_option: selectedIdx,
            question_text: quizData.question,
            page_number: currentPage
          }, card);
        });
      });
    }
  }

  async function submitQuizPayload(payload, cardElement) {
    try {
      const res = await fetch('/api/quiz/submit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error?.message || 'Không thể gửi câu trả lời.');
      }

      if (data.is_correct) {
        cardElement.style.borderColor = "#10b981";
        cardElement.innerHTML += `
          <div style="margin-top:12px; padding:10px; background:#ecfdf5; border-radius:6px; color:#047857; font-weight:600; font-size:13px;">
            ${data.feedback}
          </div>
        `;
        activeNodeBadge.textContent = "✓ Kết thúc lượt";
        activeNodeBadge.style.background = "#dcfce7";
        if (data.default_suggestions && data.default_suggestions.length > 0) {
          renderFollowupChips(data.default_suggestions);
        }
      } else {
        cardElement.style.borderColor = "#f43f5e";
        if (data.misconception) renderMisconceptionCard(data.misconception);
        if (data.default_suggestions) renderFollowupChips(data.default_suggestions);
      }
    } catch (err) {
      console.error('Quiz submit error:', err);
    }
  }

  // Tool Render 3: Misconception Detection Card
  function renderMisconceptionCard(misconceptionData) {
    const card = document.createElement('div');
    card.className = 'misconception-card';
    card.innerHTML = `
      <div class="misconception-title"><i class="fa-solid fa-triangle-exclamation"></i> Misconception Detection (Phát hiện điểm nhầm lẫn)</div>
      <p style="font-size:13px; font-weight:600; margin-bottom:8px;">${misconceptionData.misconception_point}</p>
      <div style="font-size:13px; margin-bottom:8px;">${misconceptionData.re_explanation}</div>
      <div style="font-size:13px; color:#451a03; background:#fffbe8; padding:8px; border-radius:6px;">${misconceptionData.new_example}</div>
    `;
    chatMessages.appendChild(card);
    chatMessages.scrollTop = chatMessages.scrollHeight;

    if (misconceptionData.recheck_question) {
      renderQuizCard(misconceptionData.recheck_question);
    }
  }

  // Tool Render 4: Follow-up Suggestion Chips
  function renderFollowupChips(suggestions) {
    if (!suggestions || suggestions.length === 0) return;

    const container = document.createElement('div');
    container.className = 'chips-container';
    container.innerHTML = `
      <div style="width:100%; font-size:11px; color:#64748b; font-weight:700;">💡 GỢI Ý CÂU HỎI ĐÀO SÂU:</div>
      ${suggestions.map(s => `<button class="suggestion-chip">${s}</button>`).join('')}
    `;
    chatMessages.appendChild(container);
    chatMessages.scrollTop = chatMessages.scrollHeight;

    container.querySelectorAll('.suggestion-chip').forEach(chip => {
      chip.addEventListener('click', () => {
        sendMessage(chip.textContent);
      });
    });
  }

  // Listeners
  sendBtn.addEventListener('click', () => sendMessage());
  chatInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') sendMessage();
  });

  // 6. Resizer Handle Logic
  let isResizing = false;
  resizer.addEventListener('mousedown', (e) => {
    isResizing = true;
    document.body.style.cursor = 'col-resize';
  });

  document.addEventListener('mousemove', (e) => {
    if (!isResizing) return;
    const containerWidth = document.querySelector('.app-container').clientWidth;
    const leftWidth = e.clientX;
    const rightWidth = containerWidth - leftWidth;

    if (leftWidth > 350 && rightWidth > 350) {
      leftPane.style.width = `${leftWidth}px`;
      leftPane.style.flex = 'none';
      rightPane.style.width = `${rightWidth}px`;
    }
  });

  document.addEventListener('mouseup', () => {
    isResizing = false;
    document.body.style.cursor = 'default';
  });

  // 7. Dark/Light Theme Toggle
  themeToggleBtn.addEventListener('click', () => {
    const currentTheme = document.documentElement.getAttribute('data-theme');
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', newTheme);
    themeToggleBtn.innerHTML = newTheme === 'dark' ? '<i class="fa-regular fa-sun"></i>' : '<i class="fa-regular fa-moon"></i>';
  });

  // 8. Workflow Diagram Modal
  openWfModalBtn.addEventListener('click', () => wfModal.style.display = 'flex');
  closeWfModalBtn.addEventListener('click', () => wfModal.style.display = 'none');
  wfModal.addEventListener('click', (e) => {
    if (e.target === wfModal) wfModal.style.display = 'none';
  });

  // Initialize
  applyZoom(currentZoom);
  loadSlides();
});
