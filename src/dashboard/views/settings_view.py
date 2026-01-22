import streamlit as st
from datetime import datetime
import textwrap

import base64

import base64

import base64

import base64

def render_settings():
    """
    Renders the Settings Page with a layout similar to the provided design.
    """
    
    # --- Custom CSS for File Uploader Minimization ---
    st.markdown("""
    <style>
    /* Compact File Uploader */
    div[data-testid="stFileUploader"] {
        width: 100%;
    }
    div[data-testid="stFileUploader"] section {
        padding: 0;
        min-height: 0;
        background-color: transparent;
        border: none;
    }
    div[data-testid="stFileUploader"] section > div {
        padding-top: 0;
        padding-bottom: 0;
    }
    div[data-testid="stFileUploader"] button[kind="secondary"] {
        width: 100%;
        border-color: #CBD5E1; 
        color: #64748B;
        padding-top: 0.25rem;
        padding-bottom: 0.25rem;
    }
    /* Hide the 'Drag and drop file here' text and limit text */
    div[data-testid="stFileUploader"] span, 
    div[data-testid="stFileUploader"] small,
    section[data-testid="stFileUploaderDropzone"] span,
    section[data-testid="stFileUploaderDropzone"] small {
        display: none !important;
    }
    
    /* Fix Read-Only Input Visibility */
    .stTextInput input:disabled {
        color: #1E293B !important; /* Slate 800 - Very dark gray */
        -webkit-text-fill-color: #1E293B !important;
        opacity: 1 !important;
        background-color: #F1F5F9 !important; /* Slate 100 */
        font-weight: 500 !important;
        cursor: not-allowed;
    }
    </style>
    """, unsafe_allow_html=True)

    # Retrieve User Info from Session
    current_username = st.session_state.get("username", "System Administrator")
    current_email = st.session_state.get("user_email", "")
    # Retrieve avatar from session request (persisted base64 string)
    current_avatar = st.session_state.get("user_avatar", None)
    
    # --- Breadcrumbs & Header ---
    st.markdown(textwrap.dedent("""
    <div style="margin-bottom: 24px;">
      <div style="display: flex; align-items: center; gap: 8px; color: #64748B; font-size: 0.85rem; margin-bottom: 8px;">
        <span>Dashboard</span>
        <span class="material-symbols-outlined" style="font-size: 14px;">chevron_right</span>
        <span style="color: #0F172A; font-weight: 500;">Settings</span>
      </div>
      <h1 style="color: #0F172A; font-size: 1.8rem; font-weight: 800; margin: 0;">General Settings</h1>
      <p style="color: #64748B; margin-top: 4px;">Configure your system preferences and data processing parameters.</p>
    </div>
    """), unsafe_allow_html=True)

    # --- Main Layout (Sidebar Menu vs Content) ---
    col_nav, col_content = st.columns([1, 3.5])

    with col_nav:
        st.markdown(textwrap.dedent("""
        <div style="position: sticky; top: 20px;">
          <div style="font-size: 0.7rem; font-weight: 700; color: #94A3B8; text-transform: uppercase; margin-bottom: 8px; padding-left: 12px;">Settings Menu</div>
          <div class="settings-nav-item active">
            <span class="material-symbols-outlined">settings</span> General
          </div>
          <div class="settings-nav-item">
            <span class="material-symbols-outlined">person</span> Account
          </div>
          <div class="settings-nav-item">
            <span class="material-symbols-outlined">terminal</span> Data Processing
          </div>
          <div class="settings-nav-item">
            <span class="material-symbols-outlined">notifications_active</span> Notifications
          </div>
          <div class="settings-nav-item">
            <span class="material-symbols-outlined">security</span> Security
          </div>
          
          <div style="margin-top: 20px; border-top: 1px solid #E2E8F0; padding-top: 16px;">
            <div style="display: flex; gap: 12px; padding: 8px 12px; align-items: center;">
              <div style="width: 36px; height: 36px; background: rgba(13, 148, 136, 0.1); border-radius: 50%; display: flex; align-items: center; justify-content: center; color: #0D9488;">
                <span class="material-symbols-outlined" style="font-size: 20px;">analytics</span>
              </div>
              <div style="overflow: hidden;">
                <div style="font-size: 0.75rem; font-weight: 700; color: #0F172A;">LogFlow Analytics</div>
                <div style="font-size: 0.65rem; color: #64748B; font-weight: 500;">v2.4.1 Stable</div>
              </div>
            </div>
          </div>
        </div>
        """), unsafe_allow_html=True)

    with col_content:
        # --- User Profile Section ---
        with st.container():
            st.markdown('<div class="settings-card">', unsafe_allow_html=True)
            st.markdown('<div class="settings-card-title">User Profile</div>', unsafe_allow_html=True)
            
            c_profile_icon, c_profile_inputs = st.columns([1, 4])
            
            with c_profile_icon:
                # --- HIDDEN FILE UPLOADER HACK ---
                if "show_uploader" not in st.session_state:
                    st.session_state.show_uploader = False

                # Determine what to show
                avatar_style = "background: #F1F5F9; display: flex; align-items: center; justify-content: center;"
                icon_content = '<span class="material-symbols-outlined" style="font-size: 32px; color: #94A3B8;">person</span>'
                
                uploaded_file = None
                new_avatar_b64 = None

                if current_avatar:
                     avatar_style = f"background-image: url('data:image/png;base64,{current_avatar}'); background-size: cover; background-position: center;"
                     icon_content = ""
                
                # Render Avatar
                # We use a button that looks like the edit icon to toggle visibility
                c_av_view, c_av_edit = st.columns([1, 0.1])
                with c_av_view:
                     st.markdown(textwrap.dedent(f"""
                    <div style="position: relative; width: 80px; margin: 0 auto 10px auto;">
                      <div style="width: 80px; height: 80px; border-radius: 50%; border: 2px dashed #CBD5E1; overflow: hidden; {avatar_style}">
                        {icon_content}
                      </div>
                    </div>
                    """), unsafe_allow_html=True)
                
                # To avoid the "Directly open open folder" issue which might mean an intrusive UI:
                # We will show the toggle button "Edit Photo".
                # When clicked, we show the uploader, BUT we apply the CSS above to make it minimal.
                
                if st.button("Edit Photo", key="btn_toggle_upload", use_container_width=True):
                    st.session_state.show_uploader = not st.session_state.show_uploader
                    st.rerun()

                # Only show uploader if enabled
                if st.session_state.show_uploader:
                    # Renders as a minimal "Browse files" button due to CSS
                    uploaded_file = st.file_uploader("Upload Avatar", type=['png', 'jpg', 'jpeg'], label_visibility="collapsed")
                    if uploaded_file:
                        bytes_data = uploaded_file.getvalue()
                        new_avatar_b64 = base64.b64encode(bytes_data).decode()
                        # Update preview immediately
                        # We also updated persisted state in the main update loop, but for immediate preview:
                        avatar_style = f"background-image: url('data:image/png;base64,{new_avatar_b64}'); background-size: cover; background-position: center;"
                        icon_content = ""
                        # Optionally auto-hide uploader? No, let user confirm.

            with c_profile_inputs:
                c1, c2 = st.columns(2)
                with c1:
                    new_name = st.text_input("Full Name", value=current_username, disabled=True)
                with c2:
                    new_email = st.text_input("Email Address", value=current_email, disabled=True)
            
            st.markdown('</div>', unsafe_allow_html=True)

        # --- Site Configuration Section ---
        with st.container():
            st.markdown('<div class="settings-card">', unsafe_allow_html=True)
            st.markdown('<div class="settings-card-title">Site Configuration</div>', unsafe_allow_html=True)
            
            c1, c2 = st.columns(2)
            with c1:
                st.text_input("Dashboard Name", value="Distributed Log Analytics Dashboard")
            with c2:
                st.selectbox("System Timezone", ["UTC (Coordinated Universal Time)", "EST (Eastern Standard Time)", "PST (Pacific Standard Time)"], index=0)
            
            st.markdown('</div>', unsafe_allow_html=True)

        # --- Theme Preferences Section ---
        with st.container():
            st.markdown('<div class="settings-card">', unsafe_allow_html=True)
            st.markdown('<div class="settings-card-title">Theme Preferences</div>', unsafe_allow_html=True)
            
            # Interface Mode
            c_lbl, c_ctrl = st.columns([2, 1])
            with c_lbl:
                st.markdown("**Interface Mode**")
                st.caption("Toggle between light and dark display modes.")
            with c_ctrl:
                mode = st.radio("Interface Mode", ["Light", "Dark"], horizontal=True, label_visibility="collapsed", index=0)

            st.markdown('<div style="height: 1px; background: #F1F5F9; margin: 16px 0;"></div>', unsafe_allow_html=True)

            # Brand Color
            c_lbl2, c_ctrl2 = st.columns([2, 1])
            with c_lbl2:
                st.markdown("**Brand Primary Color**")
                st.caption("Customize the accent color for your dashboard.")
            with c_ctrl2:
                # Mock color picker using purely visual HTML as custom inputs are hard
                st.markdown(textwrap.dedent("""
                <div style="display: flex; gap: 8px;">
                  <div style="width: 24px; height: 24px; background: #0D9488; border-radius: 50%; border: 2px solid white; box-shadow: 0 0 0 2px #0D9488; cursor: pointer;"></div>
                  <div style="width: 24px; height: 24px; background: #10B981; border-radius: 50%; cursor: pointer; border: 1px solid #E2E8F0;"></div>
                  <div style="width: 24px; height: 24px; background: #F59E0B; border-radius: 50%; cursor: pointer; border: 1px solid #E2E8F0;"></div>
                  <div style="width: 24px; height: 24px; background: #F43F5E; border-radius: 50%; cursor: pointer; border: 1px solid #E2E8F0;"></div>
                </div>
                """), unsafe_allow_html=True)
                
            st.markdown('</div>', unsafe_allow_html=True)

        # --- PySpark Configuration ---
        with st.container():
            st.markdown('<div class="settings-card">', unsafe_allow_html=True)
            st.markdown(textwrap.dedent("""
            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 20px;">
              <div class="settings-card-title" style="margin-bottom: 0;">PySpark Configuration</div>
              <span style="background: rgba(13, 148, 136, 0.1); color: #0D9488; font-size: 10px; font-weight: 800; padding: 2px 6px; border-radius: 4px; text-transform: uppercase;">Experimental</span>
            </div>
            """), unsafe_allow_html=True)
            
            c1, c2 = st.columns(2)
            with c1:
                st.text_input("Spark Master URL", placeholder="spark://master:7077")
            with c2:
                st.number_input("Log Refresh Interval (seconds)", value=30, min_value=5)

            st.markdown(textwrap.dedent("""
            <div style="margin-top: 16px; display: flex; gap: 12px; padding: 12px; background: rgba(13, 148, 136, 0.05); border-radius: 8px; border: 1px solid rgba(13, 148, 136, 0.2);">
              <span class="material-symbols-outlined" style="color: #0D9488; font-size: 20px;">info</span>
              <div style="font-size: 0.75rem; color: #0F766E; font-weight: 500; line-height: 1.5;">
                Changes to the Spark configuration will require a restart of the streaming job cluster. Ensure no active jobs are processing critical logs before saving.
              </div>
            </div>
            """), unsafe_allow_html=True)
            
            st.markdown('</div>', unsafe_allow_html=True)

        # --- Footer Actions ---
        st.markdown(textwrap.dedent("""
        <div style="margin-top: 24px; border-top: 1px solid #E2E8F0; padding-top: 24px; display: flex; justify-content: flex-end; gap: 12px;">
        """), unsafe_allow_html=True)
        
        col_actions_spacer, col_actions_btns = st.columns([3, 2])
        with col_actions_btns:
            # Using columns for buttons to align right
            b_cancel, b_save = st.columns(2)
            with b_cancel:
                if st.button("Discard Changes", type="secondary", use_container_width=True):
                    # Reset UI state
                    st.session_state.show_uploader = False
                    st.session_state.page = "dashboard"
                    st.rerun()
            with b_save:
                if st.button("Save Changes", type="primary", use_container_width=True):
                    # Update Session State (Mock Persistence)
                    
                    # If display_email was derived from username, we update username.
                    if "@" in new_email:
                        st.session_state.username = new_email
                    else:
                        st.session_state.username = new_name # Fallback if they put name in?
                        st.session_state.user_email = new_email
                    
                    if new_avatar_b64:
                        st.session_state.user_avatar = new_avatar_b64
                    
                    # Reset UI state
                    st.session_state.show_uploader = False
                    
                    st.toast("Settings saved successfully!", icon="✅")
                    st.rerun()
