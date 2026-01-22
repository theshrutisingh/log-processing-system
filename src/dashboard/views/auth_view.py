import streamlit as st
import auth
import otp_utils

# --- CALLBACKS FOR INSTANT TRANSITIONS ---
def handle_send_otp():
    """Callback to handle sending OTP and transitioning to OTP step"""
    email = st.session_state.get("fp_email_in", "").strip()
    if email:
        user = auth.check_email_exists(email)
        if user:
            otp = otp_utils.generate_otp()
            if otp_utils.send_otp_email(email, otp):
                st.session_state.fp_otp_val = otp
                st.session_state.fp_email_val = email
                st.session_state.fp_step = "otp"
                st.success("Reset Link Sent!")
            else:
                st.error("Failed to send email.")
        else:
            st.error("Email not found.")
    else:
        st.warning("Please enter an email address")

def handle_verify_otp():
    """Callback to verify OTP and transition to reset step"""
    user_otp = st.session_state.get("fp_otp_in", "")
    if user_otp == st.session_state.get("fp_otp_val"):
        st.session_state.fp_step = "reset"
    else:
        st.error("Invalid OTP")

def handle_resend_otp():
    """Callback to resend OTP"""
    new_otp = otp_utils.generate_otp()
    if otp_utils.send_otp_email(st.session_state.fp_email_val, new_otp):
        st.session_state.fp_otp_val = new_otp
        st.toast("New OTP sent!")

def handle_reset_password():
    """Callback to update password and transition to success step"""
    new_pw = st.session_state.get("fp_new_pw", "")
    conf_pw = st.session_state.get("fp_conf_pw", "")
    
    if new_pw and new_pw == conf_pw:
        if auth.update_password(st.session_state.fp_email_val, new_pw):
            st.session_state.fp_step = "success"
        else:
            st.error("Database Error")
    else:
        st.error("Passwords do not match")

def handle_back_to_login():
    """Callback to return to login via button"""
    st.session_state.auth_mode = "login"
    st.session_state.pop("fp_step", None)
    st.session_state.pop("fp_otp_val", None)
    st.session_state.pop("fp_email_val", None)

def login_page():
    # Initialize Auth Mode
    if "auth_mode" not in st.session_state:
        st.session_state.auth_mode = "login"

    def toggle_mode():
        st.session_state.auth_mode = "signup" if st.session_state.auth_mode == "login" else "login"

    def set_forgot_password():
        st.session_state.auth_mode = "forgot_password"
        st.session_state.fp_step = "email" # email, otp, reset

    def back_to_login():
        st.session_state.auth_mode = "login"

    # CSS is already loaded by main app via style.css
    
    # Center the card
    col1, col2, col3 = st.columns([1, 1.2, 1])
    
    with col2:
        if st.session_state.auth_mode == "login":
            # Inputs
            with st.form("login_form", clear_on_submit=False):
                # Header
                st.markdown("""
                <div class="auth-card-header">
                    <div class="lock-icon">🔒</div>
                </div>
                <div style="text-align: center; margin-bottom: 24px;">
                    <h2 style="color: #1E293B; margin: 0; font-size: 1.5rem; font-weight: 700;">Log Analytics Portal</h2>
                    <p style="color: #64748B; font-size: 0.9rem; margin-top: 8px;">Secure access to your distributed logging infrastructure.</p>
                </div>
                """, unsafe_allow_html=True)

                st.markdown("**Username or Email**")
                username = st.text_input("Username", placeholder="name@company.com", label_visibility="collapsed", key="login_user")
                
                st.markdown("<div style='height: 12px'></div>", unsafe_allow_html=True)
                
                st.markdown("**Password**")
                password = st.text_input("Password", type="password", placeholder="••••••••", label_visibility="collapsed", key="login_pass")
                
                st.markdown("<div style='height: 16px'></div>", unsafe_allow_html=True)

                # Remember Me & Forgot Password
                c_rem, c_forgot = st.columns(2)
                with c_rem:
                        st.checkbox("Remember me")
                with c_forgot:
                        # Use button for correct state transition
                        if st.form_submit_button("Forgot password?", type="secondary", use_container_width=True):
                            set_forgot_password()
                            st.rerun()

                st.markdown("<div style='height: 8px'></div>", unsafe_allow_html=True)
                
                submitted = st.form_submit_button("Sign In →", use_container_width=True, type="primary")

            if submitted:
                if auth.check_credentials(username, password):
                    st.session_state.logged_in = True
                    # Retrieve canonical username (in case login was via email)
                    real_username = auth.get_canonical_username(username)
                    st.session_state.username = real_username
                    st.session_state.user_email = auth.get_user_email(real_username)
                    st.rerun()
                else:
                    st.error("Incorrect username or password")
            
            # Footer Toggle
            st.markdown("<div style='text-align: center; margin-top: 16px; color: #64748B; font-size: 0.9rem;'>Don't have an account?</div>", unsafe_allow_html=True)
            if st.button("Sign Up", type="secondary", use_container_width=True):
                toggle_mode()
                st.rerun()

        elif st.session_state.auth_mode == "forgot_password":
             # Initialize FP Step
             if "fp_step" not in st.session_state: st.session_state.fp_step = "email"

             with st.form("forgot_password_form", clear_on_submit=False):
                 
                 # 1. Email Step
                 if st.session_state.fp_step == "email":
                     st.markdown("""<style>div[data-testid="InputInstructions"] { display: none; }</style>""", unsafe_allow_html=True)
                     st.markdown("""
                    <div class="auth-card-header">
                        <div class="lock-icon">↺</div>
                    </div>
                    <div style="text-align: center; margin-bottom: 32px;">
                        <h2 style="color: #1E293B; margin: 0; font-size: 1.6rem; font-weight: 700;">Forgot Password?</h2>
                        <p style="color: #64748B; font-size: 0.9rem; margin-top: 12px; line-height: 1.5;">
                            Enter your registered email address to receive a<br>password reset OTP.
                        </p>
                    </div>
                    """, unsafe_allow_html=True)

                     st.markdown("**Email Address**")
                     st.text_input("Email", placeholder="Enter your email address", label_visibility="collapsed", key="fp_email_in")
                     st.markdown("<div style='height: 24px'></div>", unsafe_allow_html=True)
                     
                     st.form_submit_button("Send OTP ➤", use_container_width=True, type="primary", on_click=handle_send_otp)

                 # 2. OTP Step
                 elif st.session_state.fp_step == "otp":
                     st.markdown("""
                     <style>
                        div[data-testid="InputInstructions"] { display: none; }
                        div[data-testid="stTextInput"] { width: 320px !important; margin: 0 auto !important; }
                        div[data-testid="stTextInput"] input {
                            text-align: center !important; font-size: 32px !important; font-weight: 700 !important;
                            font-family: 'Inter', sans-serif !important; letter-spacing: 16px !important;
                            color: #1E293B !important; caret-color: #3B82F6 !important;
                            background-color: #F8FAFC !important; border: 2px solid #E2E8F0 !important;
                            border-radius: 12px !important; padding: 16px 0 !important; height: auto !important;
                            transition: all 0.2s ease !important;
                        }
                        div[data-testid="stTextInput"] input:focus {
                            border-color: #3B82F6 !important; background-color: #FFFFFF !important;
                            box-shadow: 0 4px 12px rgba(59, 130, 246, 0.15) !important;
                        }
                     </style>
                     """, unsafe_allow_html=True)

                     st.markdown("""
                    <div class="auth-card-header">
                        <div class="lock-icon">🛡️</div>
                    </div>
                    <div style="text-align: center; margin-bottom: 24px;">
                        <h2 style="color: #1E293B; margin: 0; font-size: 1.6rem; font-weight: 700;">Enter OTP</h2>
                        <p style="color: #64748B; font-size: 0.9rem; margin-top: 8px;">
                            Enter the 6-digit code sent to your email
                        </p>
                    </div>
                    """, unsafe_allow_html=True)

                     st.text_input("OTP", placeholder="• • • • • •", label_visibility="collapsed", key="fp_otp_in", max_chars=6)
                     st.markdown("<div style='height: 24px'></div>", unsafe_allow_html=True)
                     
                     st.form_submit_button("Verify Code", type="primary", use_container_width=True, on_click=handle_verify_otp)
                    
                     st.markdown("<div style='height: 12px'></div>", unsafe_allow_html=True)

                     # Resend Link Style
                     c_text, c_btn = st.columns([1.4, 1])
                     with c_text:
                         st.markdown("<div style='text-align: right; color: #64748B; padding-top: 8px; font-size: 0.9rem;'>Didn't receive the code?</div>", unsafe_allow_html=True)
                     with c_btn:
                          st.form_submit_button("Resend Code", type="secondary", use_container_width=False, on_click=handle_resend_otp)

                 # 3. Reset Step
                 elif st.session_state.fp_step == "reset":
                     st.markdown("""
                     <style>
                        div[data-testid="InputInstructions"] { display: none; }
                     </style>
                     <div style="text-align: left; margin-bottom: 20px; padding-top: 10px;">
                         <h3 style="color: #334155; margin: 0; font-size: 1.2rem; font-weight: 600;">New Password</h3>
                     </div>
                     """, unsafe_allow_html=True)

                     st.text_input("New Password", type="password", key="fp_new_pw")
                     st.text_input("Confirm Password", type="password", key="fp_conf_pw")
                     st.markdown("<div style='height: 24px'></div>", unsafe_allow_html=True)
                     
                     st.form_submit_button("Reset Password", type="primary", use_container_width=True, on_click=handle_reset_password)

                 # 4. Success Step
                 elif st.session_state.fp_step == "success":
                      st.markdown("""
                      <div style="text-align: center; padding: 20px 0;">
                        <div style="
                            width: 80px; height: 80px; background-color: #DCFCE7; 
                            border-radius: 50%; display: flex; align-items: center; 
                            justify-content: center; margin: 0 auto 24px auto;
                        ">
                            <span style="font-size: 40px; color: #16A34A;">✔</span>
                        </div>
                        <h2 style="color: #1E293B; margin: 0 0 16px 0; font-size: 1.5rem; font-weight: 700;">Password Updated!</h2>
                        <p style="color: #64748B; font-size: 0.95rem; line-height: 1.6; margin-bottom: 32px;">
                            Your password has been successfully changed. You can now log in with your new credentials. A confirmation email has been sent to your inbox.
                        </p>
                      </div>
                      """, unsafe_allow_html=True)
                      
                      st.form_submit_button("Back to Login", type="primary", use_container_width=True, on_click=handle_back_to_login)

                      st.markdown("""
                      <div style="text-align: center; margin-top: 24px;">
                        <span style="color: #94A3B8; font-size: 0.85rem;">Didn't perform this action? <a href="#" style="color: #3B82F6; text-decoration: none;">Contact Security</a></span>
                      </div>
                      """, unsafe_allow_html=True)

             st.markdown("<div style='text-align: center; margin-top: 16px;'></div>", unsafe_allow_html=True)
             if st.button("← Back to Login", use_container_width=True, type="secondary"):
                 back_to_login()
                 st.rerun()

        else:
            with st.form("signup_form", clear_on_submit=False):
                # Sign Up Mode
                st.markdown("""
                <div class="auth-card-header">
                    <div class="lock-icon">👤</div>
                </div>
                <div style="text-align: center; margin-bottom: 24px;">
                    <h2 style="color: #1E293B; margin: 0; font-size: 1.5rem; font-weight: 700;">Create Account</h2>
                    <p style="color: #64748B; font-size: 0.9rem; margin-top: 8px;">Join your team today.</p>
                </div>
                """, unsafe_allow_html=True)

                st.markdown("**Choose Username**")
                new_user = st.text_input("User", placeholder="username", label_visibility="collapsed", key="signup_user")
                
                st.markdown("<div style='height: 12px'></div>", unsafe_allow_html=True)

                st.markdown("**Email Address**")
                new_email = st.text_input("Email", placeholder="name@company.com", label_visibility="collapsed", key="signup_email")
                
                st.markdown("<div style='height: 12px'></div>", unsafe_allow_html=True)
                
                st.markdown("**Choose Password**")
                new_pass = st.text_input("Pass", type="password", placeholder="••••••••", label_visibility="collapsed", key="signup_pass")
                
                st.markdown("<div style='height: 24px'></div>", unsafe_allow_html=True)

                submitted_signup = st.form_submit_button("Create Account", use_container_width=True, type="primary")
            
            if submitted_signup:
                    if not new_user or not new_pass:
                        st.warning("Username and password required")
                    elif auth.create_user(new_user, new_pass, new_email):
                        st.success("Account created! Please sign in.")
                        st.session_state.auth_mode = "login"
                        st.rerun()
                    else:
                        st.error("Username already exists")
            
            st.markdown("<div style='text-align: center; margin-top: 16px; color: #64748B; font-size: 0.9rem;'>Already have an account?</div>", unsafe_allow_html=True)
            if st.button("Back to Login", type="secondary", use_container_width=True):
                toggle_mode()
                st.rerun()

    # Footer
    st.markdown("""
        <div style="text-align: center; margin-top: 48px; color: #94A3B8; font-size: 0.8rem; font-weight: 500;">
            ⚡ Powered by Apache Spark & PySpark Runtime v3.5
        </div>
        <div style="text-align: center; margin-top: 60px; color: #CBD5E1; font-size: 0.75rem;">
            © 2024 Log Analytics Infrastructure. All systems secure.
        </div>
    """, unsafe_allow_html=True)
