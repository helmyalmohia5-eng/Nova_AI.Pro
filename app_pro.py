import time
import io
import streamlit as st
from google import genai
from PIL import Image
from gtts import gTTS
from pypdf import PdfReader

# =============================================================
# 1. تهيئة الصفحة والهوية البصرية المستقلة Nova ✨
# =============================================================
st.set_page_config(
    page_title="Nova ✨",
    page_icon="✨",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# تطهير الواجهة بالكامل وتنسيق التبويبات كشريط تطبيق حديث
hide_streamlit_style = """
    <style>
    #MainMenu {visibility: hidden;}
    header {visibility: hidden;}
    footer {visibility: hidden;}
    [data-testid="stSidebar"] {display: none;}
    [data-testid="collapsedControl"] {display: none;}
    [data-testid="stHeader"] {display: none;}
    [data-testid="stToolbar"] {display: none;}
    
    .main-header {
        text-align: center;
        font-size: 3rem;
        font-weight: 900;
        background: linear-gradient(90deg, #4A90E2, #50E3C2, #4A90E2);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 1rem;
    }
    
    .welcome-card {
        background: linear-gradient(145deg, #1e222d, #252a38);
        border-right: 5px solid #50E3C2;
        padding: 20px;
        border-radius: 12px;
        margin-bottom: 20px;
        color: #e2e8f0;
        font-size: 1.05rem;
        box-shadow: 0 4px 15px rgba(0,0,0,0.2);
    }
    
    .stTabs [data-baseweb="tab-list"] {
        display: flex;
        justify-content: center;
        background-color: #1a1d24;
        border-radius: 15px;
        padding: 10px;
        gap: 10px;
        flex-wrap: wrap;
        box-shadow: 0 4px 10px rgba(0,0,0,0.3);
    }
    .stTabs [data-baseweb="tab"] {
        background-color: #2b3040;
        border-radius: 10px;
        padding: 10px 20px;
        color: #a0aec0;
        font-weight: bold;
        border: 1px solid transparent;
        transition: all 0.3s ease;
    }
    .stTabs [data-baseweb="tab"]:hover {
        background-color: #3a4155;
        color: white;
    }
    .stTabs [aria-selected="true"] {
        background: linear-gradient(45deg, #4A90E2, #50E3C2);
        color: white !important;
        border: none;
        box-shadow: 0 2px 8px rgba(74, 144, 226, 0.4);
    }
    
    /* تنسيق خاص لقسم حول المنصة */
    .about-section {
        background-color: #1e222d;
        padding: 25px;
        border-radius: 10px;
        border-left: 4px solid #4A90E2;
        margin-top: 15px;
    }
    </style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

# =============================================================
# 2. إدارة المفاتيح والمعالجة الصامتة لـ 503 و 429
# =============================================================
API_KEYS = st.secrets.get("API_KEYS", [])

if "key_index" not in st.session_state:
    st.session_state.key_index = 0

class SmartClient:
    @property
    def models(self):
        class ModelHandler:
            def generate_content(self_inner, *args, **kwargs):
                if not API_KEYS:
                    raise Exception("لم يتم العثور على مصفوفة API_KEYS في Secrets.")
                
                max_attempts = len(API_KEYS) * 2
                for attempt in range(max_attempts):
                    current_key = API_KEYS[st.session_state.key_index % len(API_KEYS)]
                    real_client = genai.Client(api_key=current_key)
                    try:
                        return real_client.models.generate_content(*args, **kwargs)
                    except Exception as e:
                        err_str = str(e)
                        if any(code in err_str for code in ["503", "UNAVAILABLE", "429", "RESOURCE_EXHAUSTED", "500", "DEADLINE_EXCEEDED"]):
                            time.sleep(1.0)
                            st.session_state.key_index = (st.session_state.key_index + 1) % len(API_KEYS)
                            continue
                        raise e
                raise Exception("الخوادم تشهد ضغطاً مؤقتاً. يرجى الضغط على زر الإرسال مرة أخرى.")
        return ModelHandler()

client = SmartClient()

# =============================================================
# 3. معالجة 404 واكتشاف المحرك الشغال تلقائياً
# =============================================================
@st.cache_resource
def get_first_available_model(_client):
    try:
        current_key = API_KEYS[st.session_state.key_index % len(API_KEYS)] if API_KEYS else None
        if current_key:
            test_client = genai.Client(api_key=current_key)
            for m in test_client.models.list():
                if "generateContent" in getattr(m, "supported_generation_methods", []):
                    name = m.name.replace("models/", "")
                    if "flash" in name:
                        return name
    except Exception:
        pass
    return "gemini-3.6-flash"

ACTIVE_MODEL = get_first_available_model(client)

def generate_ai_response(client, prompt, image=None):
    candidate_models = [ACTIVE_MODEL, "gemini-3.6-flash", "gemini-2.5-flash", "gemini-1.5-flash"]
    seen = set()
    candidate_models = [m for m in candidate_models if not (m in seen or seen.add(m))]
    
    last_err = None
    for model_name in candidate_models:
        try:
            contents = [image, prompt] if image else prompt
            res = client.models.generate_content(model=model_name, contents=contents)
            return res.text
        except Exception as e:
            last_err = e
            err_str = str(e)
            if "404" in err_str or "NOT_FOUND" in err_str:
                continue
            else:
                raise e
    raise Exception(f"فشل الطلب عبر النماذج المتاحة: {last_err}")

# =============================================================
# 4. تهيئة الجلسة والدوال المساعدة
# =============================================================
if "pdf_text" not in st.session_state:
    st.session_state["pdf_text"] = ""
if "chat_history" not in st.session_state:
    st.session_state["chat_history"] = []
if "user_name" not in st.session_state:
    if hasattr(st, "user") and st.user and getattr(st.user, "email", None):
        st.session_state["user_name"] = st.user.email.split("@")[0]
    else:
        st.session_state["user_name"] = ""

def extract_text_from_pdf(pdf_file):
    try:
        reader = PdfReader(pdf_file)
        extracted_text = ""
        for page in reader.pages:
            t = page.extract_text()
            if t:
                extracted_text += t + "\n"
        return extracted_text
    except Exception as e:
        st.error(f"خطأ في قراءة ملف الـ PDF: {e}")
        return ""

def text_to_speech(text):
    try:
        clean_text = text.replace("*", "").replace("#", "")[:500]
        tts = gTTS(text=clean_text, lang='ar')
        fp = io.BytesIO()
        tts.write_to_fp(fp)
        fp.seek(0)
        return fp
    except Exception:
        return None

# =============================================================
# 5. واجهة التسجيل المخصصة
# =============================================================
st.markdown('<div class="main-header">Nova ✨</div>', unsafe_allow_html=True)

if not st.session_state["user_name"]:
    st.markdown("""
    <div class="welcome-card" style="text-align: center; padding: 40px;">
        <h2 style="color: white;">مرحباً بك في منصة Nova الذكية! 🚀</h2>
        <p style="color: #a0aec0;">يرجى إدخال اسمك للبدء وتخصيص تجربة الاستخدام الخاصة بك.</p>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        name_input = st.text_input("أدخل اسمك الكريم:", key="name_entry", placeholder=" مثال :  حلمي المحيا")
        if st.button("دخول المنصة ✨", use_container_width=True, type="primary"):
            if name_input.strip():
                st.session_state["user_name"] = name_input.strip()
            else:
                st.session_state["user_name"] = "زائر Nova"
            st.rerun()
    
    # توقيع المطور في شاشة الدخول أيضاً
    st.markdown("<br><hr>", unsafe_allow_html=True)
    st.caption("✨ التطوير والملكية الفكرية: المهندس حلمي عبد الصمد محمد المحيا")
    st.stop()

# =============================================================
# 6. التبويبات الشاملة مع تعزيز هوية Nova والتبويب الجديد
# =============================================================
tab_home, tab_chat, tab_img, tab_flash, tab_map, tab_exam, tab_quiz, tab_about = st.tabs([
    "🏠 الرئيسية", 
    "💬 الدردشة", 
    "📷 تحليل الصور", 
    "🎴 المراجعة", 
    "🗺️ الخرائط", 
    "🌙 ليلة الامتحان", 
    "📝 الاختبار",
    "ℹ️ حول المنصة"
])

# التبويب الأول: إدارة الملفات والنظام
with tab_home:
    st.markdown(f"""
    <div class="welcome-card">
        ✨ <strong>مرحباً بك يا {st.session_state['user_name']}</strong><br>
        أنت الآن متصل بمنصة Nova. جميع أدوات تحليل البيانات والنصوص مجهزة لخدمتك.
    </div>
    """, unsafe_allow_html=True)
    
    col_info, col_files = st.columns(2)
    
    with col_info:
        st.subheader("⚙️ حالة النظام")
        st.success("🟢 المحرك النشط: Nova Engine 3.6 Pro")
        if st.button("👤 تغيير اسم المستخدم", use_container_width=True):
            st.session_state["user_name"] = ""
            st.rerun()
            
    with col_files:
        st.subheader("📄 إدارة المستندات (PDF)")
        uploaded_pdf = st.file_uploader("اختر ملف PDF لتحليله والإجابة منه:", type=["pdf"])
        
        if uploaded_pdf:
            if st.button("📖 قراءة ومعالجة المستند", use_container_width=True, type="primary"):
                with st.spinner("جاري استخراج النصوص بواسطة Nova..."):
                    text = extract_text_from_pdf(uploaded_pdf)
                    if text.strip():
                        st.session_state["pdf_text"] = text
                        st.success(f"تمت قراءة المستند بنجاح! ({len(text)} حرف)")
                    else:
                        st.warning("تعذر استخراج نص واضح من هذا الملف.")
        
        if st.session_state["pdf_text"]:
            st.info("📌 يوجد مستند معالج وجاهز في ذاكرة المنصة.")
            if st.button("🗑️ مسح المستند من الذاكرة", use_container_width=True):
                st.session_state["pdf_text"] = ""
                st.rerun()
    
    st.markdown("---")
    st.caption("✨ التطوير والملكية الفكرية: المهندس حلمي عبد الصمد محمد المحيا")

# التبويب الثاني: الدردشة الذكية
with tab_chat:
    col_mode, col_style = st.columns(2)
    with col_mode:
        mode = st.radio("نطاق الإجابة:", ["🌐 المعرفة العامة (Nova Engine)", "🎯 الإجابة من ملف الـ PDF فقط"])
    with col_style:
        style = st.selectbox("أسلوب الإجابة:", ["أكاديمي دقيق 🎯", "تبسيط المفاهيم 💡", "برمجي وتطبيقي 💻"])

    st.markdown("---")

    for msg in st.session_state["chat_history"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("audio"):
                st.audio(msg["audio"], format="audio/mp3")

    user_input = st.chat_input("اسأل Nova عن أي موضوع، مسألة، أو كود برمجي...")

    if user_input:
        st.session_state["chat_history"].append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        pdf_content = st.session_state.get("pdf_text", "")
        if "🎯" in mode and not pdf_content.strip():
            st.warning("⚠️ يرجى رفع ملف PDF في تبويب 'الرئيسية' أولاً.")
            st.stop()
            
        if "🌐" in mode and pdf_content.strip():
            full_prompt = f"أنت محرك الذكاء الاصطناعي Nova ✨. أجب بأسلوب {style}.\nالسؤال: {user_input}\n\n(سياق إضافي مرفق):\n{pdf_content[:15000]}"
        elif "🎯" in mode:
            full_prompt = f"أنت محرك Nova ✨. الإجابة حصراً من المستند المرفق بأسلوب {style}.\nالمستند:\n{pdf_content}\n\nالسؤال: {user_input}"
        else:
            full_prompt = f"أنت محرك الذكاء الاصطناعي Nova ✨. أجب بأسلوب {style}.\nالسؤال: {user_input}"

        with st.chat_message("assistant"):
            with st.spinner("Nova يفكر ويصيغ الإجابة... ✨"):
                try:
                    response_text = generate_ai_response(client, full_prompt)
                    st.markdown(response_text)
                    audio_fp = text_to_speech(response_text)
                    if audio_fp:
                        st.audio(audio_fp, format="audio/mp3")
                    st.session_state["chat_history"].append({"role": "assistant", "content": response_text, "audio": audio_fp})
                    st.rerun()
                except Exception as e:
                    st.error(f"حدث خطأ: {e}")

# التبويب الثالث: تحليل الصور
with tab_img:
    st.header("📷 تحليل الصور والرسم البصري")
    col_img1, col_img2 = st.columns(2)
    with col_img1:
        img_file = st.file_uploader("رفع صورة من الجهاز:", type=["jpg", "jpeg", "png"], key="img_up")
    with col_img2:
        cam_file = st.camera_input("التقط صورة بالكاميرا", key="cam_up")

    active_image = img_file or cam_file
    if active_image:
        image_obj = Image.open(active_image)
        st.image(image_obj, caption="الصورة المدخلة", use_container_width=True)
        image_prompt = st.text_area("ما المطلوب تحليله؟", value="حل المسألة واشرح التفاصيل بدقة.", key="img_prompt_text")
        if st.button("🔍 تحليل الصورة بـ Nova ✨", key="btn_img_analyze", type="primary"):
            with st.spinner("جاري تحليل العناصر البصرية..."):
                try:
                    res_text = generate_ai_response(client, image_prompt, image=image_obj)
                    st.session_state["image_result"] = res_text
                    st.session_state["image_audio"] = text_to_speech(res_text)
                except Exception as e:
                    st.error(f"خطأ: {e}")

    if "image_result" in st.session_state:
        st.success("تم التحليل بنجاح!")
        st.markdown(st.session_state["image_result"])
        if st.session_state.get("image_audio"):
            st.audio(st.session_state["image_audio"], format="audio/mp3")

# التبويب الرابع: بطاقات المراجعة
with tab_flash:
    st.header("🎴 بطاقات المراجعة الذكية")
    topic_input = st.text_input("أدخل الموضوع المراد مراجعته:", key="review_topic_input")
    if st.button("⚡ توليد البطاقات", key="btn_review_gen", type="primary"):
        pdf_content = st.session_state.get("pdf_text", "")
        prompt = f"أنشئ 5 بطاقات مراجعة بصيغة سؤال/إجابة حول: {topic_input or 'الموضوع الرئيسي'}.\nسياق اختياري:\n{pdf_content[:10000]}"
        with st.spinner("جاري إنشاء البطاقات..."):
            try:
                st.session_state["review_res"] = generate_ai_response(client, prompt)
            except Exception as e:
                st.error(f"خطأ: {e}")

    if "review_res" in st.session_state:
        st.markdown(st.session_state["review_res"])

# التبويب الخامس: خريطة المفاهيم
with tab_map:
    st.header("🗺️ خريطة المفاهيم الذهنية")
    st.info("تعتمد الخريطة على تحليل المستند المرفوع في تبويب الرئيسية.")
    if st.button("🌳 رسم خريطة المفاهيم", key="btn_map_gen", type="primary"):
        pdf_text = st.session_state.get("pdf_text", "")
        if not pdf_text:
            st.warning("يرجى رفع ملف PDF أولاً من تبويب 'الرئيسية'.")
        else:
            prompt = f"حوّل هذا النص لخريطة مفاهيم شجرية متفرعة وشاملة:\n{pdf_text[:15000]}"
            with st.spinner("جاري بناء الهيكل الشجري..."):
                try:
                    st.session_state["map_res"] = generate_ai_response(client, prompt)
                except Exception as e:
                    st.error(f"خطأ: {e}")

    if "map_res" in st.session_state:
        st.markdown(st.session_state["map_res"])

# التبويب السادس: ورقة ليلة الامتحان
with tab_exam:
    st.header("🌙 ملخص ليلة الامتحان")
    if st.button("📑 توليد الملخص الشامل", key="btn_exam_gen", type="primary"):
        pdf_text = st.session_state.get("pdf_text", "")
        prompt = f"استخرج أهم القوانين والتعاريف والأسئلة المتوقعة لليلة الامتحان من:\n{pdf_text[:20000]}"
        with st.spinner("جاري استخراج النقاط الجوهرية..."):
            try:
                st.session_state["exam_res"] = generate_ai_response(client, prompt)
            except Exception as e:
                st.error(f"خطأ: {e}")

    if "exam_res" in st.session_state:
        st.markdown(st.session_state["exam_res"])

# التبويب السابع: الاختبار التفاعلي
with tab_quiz:
    st.header("📝 اختبار تفاعلي")
    if st.button("⚙️ إنشاء الاختبار", key="btn_quiz_gen", type="primary"):
        pdf_text = st.session_state.get("pdf_text", "")
        prompt = f"بناءً على المحتوى التالي، أنشئ 3 أسئلة اختيارات متعددة (MCQ) مع توضيح الإجابة الصحيحة والتفسير في النهاية:\n{pdf_text[:15000]}"
        with st.spinner("جاري صياغة الأسئلة والتفسيرات..."):
            try:
                st.session_state["quiz_res"] = generate_ai_response(client, prompt)
            except Exception as e:
                st.error(f"خطأ: {e}")

    if "quiz_res" in st.session_state:
        st.markdown(st.session_state["quiz_res"])

# التبويب الثامن: حول المنصة (الملكية والمميزات)
with tab_about:
    st.markdown("""
    <div class="about-section">
        <h2 style="color: #50E3C2; text-align: center;">✨ منصة Nova للذكاء الاصطناعي</h2>
        <br>
        <h4 style="color: #4A90E2;">👨‍💻 المطور والمالك الرسمي:</h4>
        <p style="font-size: 1.2rem; font-weight: bold; color: white;">المهندس / حلمي عبد الصمد محمد المحيا</p>
        <hr style="border-color: #2b3040;">
        <h4 style="color: #4A90E2;">🚀 لماذا تختار منصة Nova؟</h4>
        <p style="color: #e2e8f0; line-height: 1.8;">
        تم بناء <strong>Nova</strong> لتكون بيئة أكاديمية متكاملة تضمن لك الاستفادة القصوى من الذكاء الاصطناعي بأمان وموثوقية عالية. إليك أبرز الميزات الحصرية:
        <br><br>
        ✅ <strong>دقة المعلومات (التقييد بالملفات):</strong> يمكنك إجبار المحرك على استخراج الإجابات <i>فقط</i> من ملف الـ PDF الخاص بك، مما يمنع أي تأليف أو هلوسة من الذكاء الاصطناعي.<br>
        ✅ <strong>تعدد أساليب الشرح:</strong> بضغطة زر، يمكنك تغيير أسلوب الإجابة بين "الأكاديمي الدقيق"، أو "التبسيط السلس"، أو "التطبيق البرمجي" ليناسب تخصصك.<br>
        ✅ <strong>رؤية حاسوبية متقدمة:</strong> تحليل الصور وحل المسائل المعقدة عبر الكاميرا أو رفع الصور من جهازك.<br>
        ✅ <strong>أدوات دراسية متكاملة:</strong> المنصة مزودة بأدوات احترافية لتوليد 🎴 بطاقات المراجعة (Flashcards)، ورسم 🗺️ خرائط المفاهيم الشجرية، وصناعة 📝 اختبارات تقييمية (MCQ).<br>
        ✅ <strong>منقذ "ليلة الامتحان":</strong> خوارزمية مخصصة لاستخلاص القوانين والأسئلة المتوقعة من المراجع الضخمة في ثوانٍ معدودة.<br>
        ✅ <strong>الاستقرار الفائق:</strong> مزودة بنظام ذكي للتبديل التلقائي بين الخوادم لضمان عدم توقف الخدمة عنك إطلاقاً.
        </p>
    </div>
    """, unsafe_allow_html=True)






