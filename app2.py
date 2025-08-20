"""
Streamlit app: Generate multiple choice physics/math problems using Google's Gemini for Google Forms

Setup:
  pip install streamlit google-generativeai pandas openpyxl

Run:
  export GOOGLE_API_KEY="your-key"   # or set in the app sidebar each run
  streamlit run app.py
"""

import os
import re
import textwrap
from typing import Generator

import pandas as pd
import streamlit as st

try:
    import google.generativeai as genai
except Exception as e:
    genai = None

# ------------------------------
# Streamlit Page Config
# ------------------------------
st.set_page_config(
    page_title="Мульти сонголттой бодлого үүсгэгч (Gemini)",
    page_icon="🧮",
    layout="centered",
)

st.title("🧮 Мульти сонголттой бодлого үүсгэгч — Gemini")
st.caption(
    "Textarea дээр оруулсан бодлоготой төстэй мульти сонголттой бодлогууд үүсгэнэ. "
    "Google Forms-д оруулахад зориулсан Excel файл гаргана. Google Gemini-г ашигладаг."
)

# ------------------------------
# Subject and subtopic definitions
# ------------------------------
PHYSICS_SUBTOPICS = {
    "Механик": ["Кинематик", "Динамик", "Статик", "Гравитаци", "Хөдөлгөөний хадгалалтын хууль", "Хүчний момент"],
    "Термодинамик": ["Хийн хууль", "Дулаан дамжуулалт", "Дулааны машин", "Энтропи", "Термодинамикийн хууль"],
    "Цахилгаан ба Соронз": ["Цахилгаан орон", "Цахилгаан гүйдэл", "Соронзон орон", "Цахилгаан соронзон индукц", "RC ба RL хэлхээ"],
    "Долгион ба Оптик": ["Долгионы шинж чанар", "Гэрлийн огилт", "Гэрлийн интерференц", "Гэрлийн туялзуур", "Хазайлт"],
    "Орчин үеийн физик": ["Квант механик", "Харьцангуй онол", "Атомын физик", "Цөмийн физик", "Элементар бөөмс"]
}

MATH_SUBTOPICS = {
    "Алгебр": ["Тэгшитгэл бодох", "Тэнцэтгэл биш", "Олон гишүүнт", "Комплекс тоо", "Матриц, тодорхойлогч"],
    "Геометр": ["Гурвалжин", "Дөрвөлжин", "Тойрог", "Геометр трансформац", "Стереометр"],
    "Тригонометр": ["Тригонометр функц", "Тригонометр тэгшитгэл", "Тригонометр тэнцэтгэл биш", "Инверс тригонометр функц"],
    "Математик анализ": ["Уламжлал", "Интеграл", "Дифференциал тэгшитгэл", "Функцийн судалгаа", "Ряд"],
    "Магадлал ба Статистик": ["Комбинаторик", "Магадлалын онол", "Санамсаргүй хэмжигдэхүүн", "Статистик дүн анализ", "Регрессийн анализ"]
}

# ------------------------------
# Sidebar: API Key & Settings
# ------------------------------
with st.sidebar:
    st.header("Тохиргоо")

    existing_key = os.getenv("GOOGLE_API_KEY", "")
    api_key = st.text_input(
        "Google API Key",
        type="password",
        value=existing_key,
        help=(
            "Системийн орчинд түлхүүр тохируулаагүй бол энд түр зуур оруулж болно. "
            "Энэ түлхүүр зөвхөн локал дээр тань ашиглагдана."
        ),
    )

    # Subject selection
    subject = st.selectbox(
        "Хичээл",
        ["Физик", "Математик"],
        index=0,
        help="Бодлого үүсгэх хичээлээ сонгоно уу"
    )
    
    # Subtopic selection based on subject
    if subject == "Физик":
        main_topic = st.selectbox(
            "Гол сэдэв",
            list(PHYSICS_SUBTOPICS.keys()),
            index=0
        )
        subtopic = st.selectbox(
            "Дэд сэдэв",
            PHYSICS_SUBTOPICS[main_topic],
            index=0
        )
    else:  # Математик
        main_topic = st.selectbox(
            "Гол сэдэв",
            list(MATH_SUBTOPICS.keys()),
            index=0
        )
        subtopic = st.selectbox(
            "Дэд сэдэв",
            MATH_SUBTOPICS[main_topic],
            index=0
        )

    model_name = st.selectbox(
        "Gemini загвар",
        [
            "gemini-1.5-flash",
            "gemini-1.5-pro",
        ],
        index=0,
        help=(
            "flash нь хурдан бөгөөд бага өртөгтэй, pro нь илүү чадвартай боловч удаан/үнэтэй байж болно."
        ),
    )

    temperature = st.slider(
        "Санаачилгатай байдал (temperature)", 0.0, 1.0, 0.7, 0.05,
        help="Ихсэх тусам төрөлжилт нэмэгдэнэ."
    )

    num_questions = st.number_input(
        "Бодлогын тоо", 
        min_value=1, 
        max_value=20, 
        value=5,
        help="Үүсгэх мульти сонголттой бодлогын тоо"
    )

    num_options = st.number_input(
        "Сонголтын тоо", 
        min_value=2, 
        max_value=6, 
        value=4,
        help="Бодлого бүрт өгөх сонголтын тоо"
    )

    st.markdown("---")
    st.subheader("Жишээ бодлого")
    
    # Example problems based on subject and subtopic
    if subject == "Физик":
        if main_topic == "Механик":
            if subtopic == "Кинематик":
                example_problem = "Машин 72 км/ц хурдтай явж байгаад 4 секундын дотор зогссон. Машины хурдатгал болон зогсох зам нь хэд вэ?"
            elif subtopic == "Динамик":
                example_problem = "15° налуу хавтгай дээр 2 кг масстай биетийг үрэлтгүй орчинд чирэхэд биед үйлчлэх татах хүч болон налуугийн дагуух хурдатгалыг ол. g=9.8 м/с²."
            else:
                example_problem = "5 кг масстай бие 10 м/с хурдтайгаар хөдөлж байгаад 2 кг масстай тайван байгаа биетэй мөргөлдөв. Мөргөлдөөн уян хатан бол угсарсан биеийн хурдыг ол."
        elif main_topic == "Цахилгаан ба Соронз":
            example_problem = "10 Ω эсэргүүцэлтэй дамжуулагчид 12 В хүчдэл залгахад гүйдэл хэд вэ? Дамжуулагчаар 5 минут явахад ялгарах дулааны хэмжээг ол."
        else:
            example_problem = "100 г масстай биеийн температур 20°C-аас 80°C хүртэл халаахад шаардагдах дулааны хэмжээг ол. Биеийн хувийн дулаан багтаамж 0.5 J/g°C байна."
    else:  # Математик
        if main_topic == "Алгебр":
            example_problem = "x² - 5x + 6 = 0 тэгшитгэлийн бодит шийдийг ол. Мөн язгууруудын нийлбэр ба үржвэрийг ол."
        elif main_topic == "Геометр":
            example_problem = "Гурвалжны талууд нь 6 см, 8 см, 10 см байна. Энэ гурвалжин тэгш өнцөгт эсэхийг шалгаад, талбайг нь ол."
        elif main_topic == "Математик анализ":
            example_problem = "y = 2x² - 4x + 1 функцийн уламжлалыг олж, экстремум цэгүүдийг тодорхойл."
        else:
            example_problem = "Нэг шоо шидэхэд: a) 4-өөс их тоо буух магадлал, b) тэгш тоо буух магадлалыг ол."
    
    if st.button("Жишээгээр дүүргэх"):
        st.session_state["problem_text"] = example_problem

# ------------------------------
# Main Input
# ------------------------------
problem_text = st.text_area(
    f"{subject} бодлогын жишээ оруулах ({main_topic} - {subtopic})",
    key="problem_text",
    height=180,
    placeholder=example_problem,
)

st.info(
    "Доорх товчийг дармагц, оруулсан бодлоготой төстэй мульти сонголттой бодлогууд үүсгэж, "
    "Google Forms-д оруулахад зориулсан Excel файл гаргана."
)

# ------------------------------
# Helpers
# ------------------------------
SYSTEM_HINT = """
Та бол {subject} багш.
Хэрэглэгчийн өгсөн бодлогын агуулга, сэдэв, түвшинд тулгуурлан төстэй шинэ мульти сонголттой бодлогууд зохионо.
Бодлогууд нь мэдээллийн хувьд логик, хэмжигдэхүүнүүд нь бодогдохоор,
бага зэрэг хувьсан өөрчлөгдсөн (тоо ба нөхцөл) байх ёстой.
""".strip()

def build_prompt(user_problem: str, n: int = 5, options_count: int = 4) -> str:
    subject_hint = SYSTEM_HINT.format(subject=subject)
    
    base = f"""
{subject_hint}

СЭДЭВ: {main_topic} - {subtopic}

Хэрэглэгчийн өгсөн бодлого:\n\n{user_problem}\n\n
ҮҮСГЭХ ДААЛГАВАР:
- Дээрх бодлоготой ижил сэдэв ({main_topic} - {subtopic}), нэг түвшний **{n}** шинэ мульти сонголттой бодлого зохионо.
- Бодлого бүрт яг {options_count} сонголт өгөх.
- Зөв хариултыг нэг сонголтод оруулах.
- Хэмжигдэхүүн, нөхцөлийг өөрчилж төрөлжүүл.
- Бодлого бүр: 1-2 догол мөр, ойлгомжтой, нэг утгатай байг.
- {subject} хичээлийн стандарт нэгж, тэмдэглэгээг ашигла.
- Давхардсан нөхцөл, тоо бүү ашигла.
""".strip()

    base += textwrap.dedent(
        f"""
\n\nГАРГАЛТЫН ХЭЛБЭР:
- JSON форматаар гаргах.
- Дараах бүтэцтэй байх:

[
  {{
    "question": "Бодлогын текст",
    "options": ["сонголт 1", "сонголт 2", "сонголт 3", "сонголт 4"],
    "correct_answer": "зөв сонголтын текст"
  }},
  ...
]

- Монгол хэлээр бич.
- ЗӨВХӨН JSON объект буцаахад анхаар. Ямар нэгэн нэмэлт текст бичихгүй.
"""
    )

    return base


def stream_gemini_text(prompt: str, model_name: str, temperature: float) -> Generator[str, None, None]:
    """Yield plain text chunks from a streaming Gemini response."""
    global genai
    if genai is None:
        yield "⚠️ google-generativeai сан суусан эсэхийг шалгана уу: `pip install google-generativeai`\n"
        return

    key = os.getenv("GOOGLE_API_KEY") or api_key
    if not key:
        yield "⚠️ API түлхүүр оруулаагүй байна. Sidebar-аас GOOGLE_API_KEY оруулна уу.\n"
        return

    genai.configure(api_key=key)

    generation_config = {
        "temperature": float(temperature),
        "max_output_tokens": 4096,
    }

    model = genai.GenerativeModel(model_name)
    try:
        response = model.generate_content(
            prompt,
            stream=True,
            generation_config=generation_config,
        )
        collected = []
        for chunk in response:
            if getattr(chunk, "text", None):
                collected.append(chunk.text)
                yield chunk.text
        st.session_state["last_generated"] = "".join(collected)
    except Exception as e:
        yield f"\n\n❌ Алдаа: {e}"


# ------------------------------
# Action Button
# ------------------------------
col1, col2 = st.columns([1, 2])
with col1:
    generate = st.button("🪄 Бодлого үүсгэх", type="primary", use_container_width=True)
with col2:
    clear = st.button("🧹 Арилгах", use_container_width=True)

if clear:
    st.session_state["problem_text"] = ""
    st.session_state["last_generated"] = ""

if api_key:
    os.environ["GOOGLE_API_KEY"] = api_key

# ------------------------------
# Generation
# ------------------------------
if generate:
    if not problem_text or problem_text.strip() == "":
        st.warning("Эх бодлогоо эхлээд бичнэ үү.")
    else:
        st.subheader(f"Үүсгэсэн {subject} бодлогууд ({main_topic} - {subtopic})")
        prompt = build_prompt(problem_text, n=num_questions, options_count=num_options)
        
        # Display the raw response
        with st.expander("Gemini-ийн хариу (JSON форматаар)"):
            response_text = st.write_stream(
                stream_gemini_text(prompt, model_name=model_name, temperature=temperature)
            )
        
        # Try to parse the JSON response
        if "last_generated" in st.session_state and st.session_state["last_generated"]:
            try:
                # Extract JSON from the response (in case there's extra text)
                json_match = re.search(r'\[\s*\{.*\}\s*\]', st.session_state["last_generated"], re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                    import json
                    questions = json.loads(json_str)
                    
                    # Create DataFrame for Excel export
                    df_data = []
                    for i, q in enumerate(questions, 1):
                        df_data.append({
                            "Асуулт": q.get("question", ""),
                            "Сонголт A": q.get("options", [""] * num_options)[0] if len(q.get("options", [])) > 0 else "",
                            "Сонголт B": q.get("options", [""] * num_options)[1] if len(q.get("options", [])) > 1 else "",
                            "Сонголт C": q.get("options", [""] * num_options)[2] if len(q.get("options", [])) > 2 else "",
                            "Сонголт D": q.get("options", [""] * num_options)[3] if len(q.get("options", [])) > 3 else "",
                            "Сонголт E": q.get("options", [""] * num_options)[4] if len(q.get("options", [])) > 4 else "",
                            "Сонголт F": q.get("options", [""] * num_options)[5] if len(q.get("options", [])) > 5 else "",
                            "Зөв хариулт": q.get("correct_answer", "")
                        })
                    
                    df = pd.DataFrame(df_data)
                    
                    # Display the questions in a nice format
                    for i, q in enumerate(questions, 1):
                        st.markdown(f"**{i}. {q.get('question', '')}**")
                        options = q.get('options', [])
                        for j, option in enumerate(options):
                            st.markdown(f"   {chr(65+j)}. {option}")
                        st.markdown(f"   **Зөв хариулт:** {q.get('correct_answer', '')}")
                        st.markdown("---")
                    
                    # Create Excel file for download
                    excel_buffer = pd.ExcelWriter("multiple_choice_questions.xlsx", engine='openpyxl')
                    df.to_excel(excel_buffer, index=False, sheet_name='Асуултууд')
                    excel_buffer.close()
                    
                    with open("multiple_choice_questions.xlsx", "rb") as f:
                        excel_data = f.read()
                    
                    st.download_button(
                        label="⬇️ Excel файл татах (Google Forms-д оруулах)",
                        data=excel_data,
                        file_name="multiple_choice_questions.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )
                else:
                    st.error("JSON форматтай хариу ирсэнгүй. Дахин оролдоно уу.")
            except Exception as e:
                st.error(f"JSON задлахад алдаа гарлаа: {e}")
                st.text("Gemini-ийн бүрэн хариу:")
                st.text(st.session_state["last_generated"])

# ------------------------------
# Footer / Tips
# ------------------------------
st.markdown(
    """
---
**Зөвлөмжүүд**
- Оруулах бодлогоо тодорхой, бүрэн өгөгтэй бичих тусам чанартай гаралт гарна.
- Төстэй биш бол temperature-г багасгаж (0.3–0.6) туршаад үзээрэй.
- Google Forms-д оруулахдаа Excel файлыг ашиглана уу.
"""
)