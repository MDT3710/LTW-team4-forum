document.addEventListener("DOMContentLoaded", function () {
    // Khởi tạo Select2 cho Chi nhánh và Phòng ban
    $('.doc-select-multiple').select2({
        placeholder: "Chọn giá trị...",
        allowClear: true,
        width: '100%'
    });
    // 1. Khai báo danh sách câu hỏi mặc định (26: Trắc nghiệm, 25: Tự luận)
    let questions = [
        {
            id: Date.now(),
            caption: "",
            question_type_id: 26, // Mặc định là Trắc nghiệm (ID = 26)
            is_required: true,
            max_choice: 1,
            choices: ["Lựa chọn 1", "Lựa chọn 2"]
        }
    ];

    const container = document.getElementById("questions-container");
    const btnAddQuestion = document.getElementById("btn-add-question");
    const form = document.getElementById("survey-form");
    const hiddenInput = document.querySelector("input[name='questions_data']");

    function renderQuestions() {
        container.innerHTML = "";

        questions.forEach((q, index) => {
            const card = document.createElement("div");
            card.style.cssText = "background: #fafcff; border: 1px solid #e5e7eb; border-radius: 8px; padding: 18px;";

            card.innerHTML = `
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                    <strong>Câu ${index + 1}</strong>
                    <div style="display: flex; gap: 10px; align-items: center;">
                        <!-- Đổi value của option thành 26 và 25 -->
                        <select class="doc-form-select" onchange="updateQuestionType(${q.id}, this.value)" style="padding: 4px 8px; font-size: 13px;">
                            <option value="26" ${q.question_type_id == 26 ? 'selected' : ''}>Trắc nghiệm</option>
                            <option value="25" ${q.question_type_id == 25 ? 'selected' : ''}>Tự luận</option>
                        </select>
                        <label style="font-size: 13px; cursor: pointer;min-width: 6rem;display: flex;align-items: center;gap: 6px;justify-content: center">
                            <input type="checkbox" ${q.is_required ? 'checked' : ''} onchange="toggleRequired(${q.id}, this.checked)"> Bắt buộc
                        </label>
                        <button type="button" onclick="removeQuestion(${q.id})" style="color: #ef4444; background: none; border: none; cursor: pointer;">Xóa</button>
                    </div>
                </div>

                <input type="text" class="doc-form-input" value="${q.caption}"
                       placeholder="Nhập nội dung câu hỏi..."
                       oninput="updateCaption(${q.id}, this.value)"
                       style="margin-bottom: 12px;">

                <!-- Hiển thị theo question_type_id = 26 -->
                ${q.question_type_id == 26 ? `
                    <div style="margin-bottom: 10px; display: flex; align-items: center; gap: 8px; font-size: 13px;">
                        <span>Số câu chọn tối đa:</span>
                        <input type="number" class="doc-form-input" value="${q.max_choice || 1}" min="1" max="${q.choices.length}"
                               onchange="updateMaxChoice(${q.id}, this.value)"
                               style="width: 70px; height: 28px; padding: 2px 6px;">
                    </div>

                    <div style="padding-left: 12px; display: flex; flex-direction: column; gap: 8px;">
                        ${q.choices.map((c, cIndex) => `
                            <div style="display: flex; gap: 8px; align-items: center;">
                                <span style="color: #6b7280;">•</span>
                                <input type="text" class="doc-form-input" value="${c}"
                                       placeholder="Lựa chọn ${cIndex + 1}"
                                       oninput="updateChoice(${q.id}, ${cIndex}, this.value)"
                                       style="height: 32px; font-size: 13px;">
                                <button type="button" onclick="removeChoice(${q.id}, ${cIndex})" style="color: #9ca3af; background: none; border: none; cursor: pointer;">×</button>
                            </div>
                        `).join('')}
                        <button type="button" onclick="addChoice(${q.id})" style="font-size: 13px; color: #2563eb; background: none; border: none; cursor: pointer; text-align: left; margin-top: 4px;">
                            + Thêm lựa chọn
                        </button>
                    </div>
                ` : `
                    <div style="color: #9ca3af; font-size: 13px; font-style: italic;">Người dùng sẽ nhập câu trả lời dạng văn bản.</div>
                    <div style="display: flex; align-items: center; gap: 8px; font-size: 13px;">
                        <span>Giới hạn ký tự (để trống nếu không giới hạn):</span>
                        <input type="number" class="doc-form-input" value="${q.max_character || ''}" min="1"
                               onchange="updateMaxCharacter(${q.id}, this.value)"
                               style="width: 100px; height: 28px; padding: 2px 6px;"
                               placeholder="VD: 500">
                    </div>
                `}
            `;
            container.appendChild(card);
        });
    }

    window.updateCaption = (id, val) => { questions.find(q => q.id === id).caption = val; };
    window.toggleRequired = (id, val) => { questions.find(q => q.id === id).is_required = val; };
    window.updateMaxChoice = (id, val) => { questions.find(q => q.id === id).max_choice = parseInt(val) || 1; };

    window.updateQuestionType = (id, val) => {
        let q = questions.find(q => q.id === id);
        q.question_type_id = parseInt(val);
        if (q.question_type_id === 26 && (!q.choices || q.choices.length === 0)) {
            q.choices = ["Lựa chọn 1", "Lựa chọn 2"];
            q.max_choice = 1;
        }
        renderQuestions();
    };

    window.addChoice = (id) => {
        questions.find(q => q.id === id).choices.push(`Lựa chọn ${questions.find(q => q.id === id).choices.length + 1}`);
        renderQuestions();
    };
    window.updateChoice = (id, cIndex, val) => { questions.find(q => q.id === id).choices[cIndex] = val; };
    window.removeChoice = (id, cIndex) => {
        questions.find(q => q.id === id).choices.splice(cIndex, 1);
        renderQuestions();
    };
    window.removeQuestion = (id) => {
        questions = questions.filter(q => q.id !== id);
        renderQuestions();
    };

    if (btnAddQuestion) {
        btnAddQuestion.addEventListener("click", function () {
            questions.push({
                id: Date.now(),
                caption: "",
                question_type_id: 26, // Thêm mới mặc định là Trắc nghiệm (ID = 26)
                is_required: true,
                max_choice: 1,
                choices: ["Lựa chọn 1", "Lựa chọn 2"]
            });
            renderQuestions();
        });
    }

    if (form) {
        form.addEventListener("submit", function () {
            if (hiddenInput) {
                hiddenInput.value = JSON.stringify(questions);
            }
        });
    }

    renderQuestions();
});