import streamlit as st
import requests

st.set_page_config(
    page_title="Student Login | Academic Portal",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# Hide sidebar completely on login page
st.markdown("""
<style>
[data-testid="stSidebar"] { display: none !important; }
[data-testid="collapsedControl"] { display: none !important; }
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }

@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif !important;
    background: #f8fafc !important;
}

.stApp {
    background: #f8fafc !important;
}

.block-container {
    padding-top: 3vh !important;
    max-width: 420px !important;
}

/* Card */
.login-card {
    background: white;
    border-radius: 20px;
    box-shadow: 0 24px 48px rgba(0,0,0,0.12), 0 8px 24px rgba(0,0,0,0.08);
    padding: 36px 36px 28px;
    position: relative;
    margin-top: 0;
}

.login-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 4px;
    background: linear-gradient(90deg, #C8860A 0%, #E8A020 50%, #F5B93A 100%);
    border-radius: 16px 16px 0 0;
}

.login-header {
    text-align: center;
    margin-bottom: 1.4rem;
    padding-bottom: 1.2rem;
    border-bottom: 1px solid #f1f5f9;
}

.login-icon {
    font-size: 36px;
    display: block;
    margin-bottom: 10px;
}

.login-title {
    color: #1e293b;
    font-size: 22px;
    font-weight: 700;
    margin: 0 0 4px 0;
    letter-spacing: -0.3px;
}

.login-sub {
    color: #94a3b8;
    font-size: 13px;
    font-weight: 400;
    letter-spacing: 0.4px;
    text-transform: uppercase;
}

.privacy-notice {
    color: #94a3b8;
    font-size: 11px;
    line-height: 1.5;
    padding: 10px 14px;
    background: #f8fafc;
    border-radius: 8px;
    border: 1px solid #f1f5f9;
    text-align: center;
    margin-top: 0.8rem;
}

.copyright {
    color: #64748b;
    font-size: 13px;
    text-align: center;
    margin-top: 12px;
}

/* Override Streamlit input styles */
div[data-testid="stTextInput"] label {
    font-size: 13px !important;
    font-weight: 600 !important;
    color: #334155 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.5px !important;
}

div[data-testid="stTextInput"] input {
    border: 2px solid #e2e8f0 !important;
    border-radius: 10px !important;
    padding: 14px 16px !important;
    font-size: 15px !important;
    background: #f8fafc !important;
    color: #1e293b !important;
}

div[data-testid="stTextInput"] input:focus {
    border-color: #E8A020 !important;
    background: white !important;
    box-shadow: 0 0 0 4px rgba(232,160,32,0.15) !important;
}

/* Login button */
div[data-testid="stButton"] button {
    width: 100% !important;
    background: linear-gradient(135deg, #C8860A 0%, #E8A020 100%) !important;
    color: white !important;
    border: none !important;
    border-radius: 10px !important;
    padding: 16px !important;
    font-size: 15px !important;
    font-weight: 600 !important;
    letter-spacing: 0.3px !important;
    transition: all 0.25s !important;
    margin-top: 8px !important;
}

div[data-testid="stButton"] button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 20px rgba(200,134,10,0.4) !important;
}

/* Error/success alerts */
div[data-testid="stAlert"] {
    border-radius: 10px !important;
}
</style>
""", unsafe_allow_html=True)

# --- Redirect if already logged in ---
if st.session_state.get("session_token") and st.session_state.get("student_id"):
    st.query_params["student_id"] = st.session_state["student_id"]
    st.switch_page("pages/dashboard.py")

# --- Card HTML ---
st.markdown("""
<div style="text-align:center; padding: 20px 0 16px 0; border-bottom: 1px solid #f1f5f9; margin-bottom: 8px;">
  <span style="font-size:32px;">🎓</span>
  <h1 style="color:#1e293b; font-size:20px; font-weight:700; margin:8px 0 4px 0; letter-spacing:-0.3px;">Academic Portal</h1>
  <p style="color:#94a3b8; font-size:11px; font-weight:400; letter-spacing:0.4px; text-transform:uppercase; margin:0;">Bahria University · Student LMS</p>
</div>
""", unsafe_allow_html=True)

# --- Form ---
reg = st.text_input("Registration Number", placeholder="e.g., 2021-CS-002")
password = st.text_input("Password", type="password", placeholder="Enter your password")

login_clicked = st.button("→  Login to Dashboard", use_container_width=True)

if login_clicked:
    if not reg.strip() or not password:
        st.error("Please fill in all fields.")
    else:
        with st.spinner("Authenticating..."):
            try:
                resp = requests.post(
                    "http://127.0.0.1:5000/login",
                    json={"registration_no": reg.strip(), "password": password},
                    timeout=10
                )
                data = resp.json()
                if data.get("success"):
                    st.session_state["session_token"] = data["session_token"]
                    st.session_state["student_id"] = str(data["student_id"])
                    st.success("Login successful! Redirecting...")
                    st.switch_page("pages/dashboard.py")
                else:
                    st.error("Invalid credentials. Please try again.")
            except requests.exceptions.ConnectionError:
                st.error("Cannot connect to server. Is auth.py running?")
            except Exception as e:
                st.error(f"Unexpected error: {e}")

st.markdown("""
<div class="privacy-notice">
    Your data is secure and encrypted. By logging in, you agree to our terms of service.
</div>
<div class="copyright">© 2026 Bahria University · Final Year Project</div>
""", unsafe_allow_html=True)