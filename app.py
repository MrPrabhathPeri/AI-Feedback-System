import streamlit as st
import pandas as pd
import google.generativeai as genai
import os
import json

# --- 1. SETUP & SECRETS ---
try:
    # Tries to get key from Streamlit Secrets (for deployment)
    API_KEY = st.secrets["GOOGLE_API_KEY"]
except FileNotFoundError:
    # If secrets file is missing, show error
    st.error("⚠️ API Key missing! Please add GOOGLE_API_KEY to your .streamlit/secrets.toml file (local) or Streamlit Cloud Secrets.")
    st.stop()

# --- 2. CONFIGURATION ---
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('models/gemini-2.0-flash') # Using the fast 2.0 model

# --- 3. DATABASE (CSV FILE) ---
DB_FILE = "reviews.csv"

if not os.path.exists(DB_FILE):
    # Initialize CSV with headers
    pd.DataFrame(columns=["rating", "review", "summary", "action", "reply", "timestamp"]).to_csv(DB_FILE, index=False)

# --- 4. AI FUNCTIONS ---
def process_review(review_text, rating):
    prompt = f"""
    You are a helpful customer support AI for Fynd.
    A user just left this {rating}-star review: "{review_text}"
    
    1. Summarize the review in 1 sentence.
    2. Suggest an internal action for the admin (e.g., "Issue Refund", "Send Thank You Note").
    3. Draft a polite, short reply to the user.
    
    Return JSON: {{"summary": "...", "action": "...", "reply": "..."}}
    """
    try:
        response = model.generate_content(prompt)
        clean_text = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_text)
    except Exception:
        return {
            "summary": "Could not analyze", 
            "action": "Manual Review Required", 
            "reply": "Thank you for your feedback!"
        }

# --- 5. UI ---
st.set_page_config(page_title="Fynd AI Feedback System", layout="wide")
st.sidebar.title("Fynd Intern Task")
page = st.sidebar.radio("Select Dashboard:", ["User Dashboard", "Admin Dashboard"])

# --- USER DASHBOARD ---
if page == "User Dashboard":
    st.title("📝 Submit Your Review")
    with st.form("review_form"):
        stars = st.slider("Rating (1-5)", 1, 5, 5)
        review_text = st.text_area("Write your review here...")
        submitted = st.form_submit_button("Submit Review")

        if submitted and review_text:
            with st.spinner("AI is processing your feedback..."):
                # 1. Call AI
                ai_result = process_review(review_text, stars)
                
                # 2. Create New Row (Corrected for Pandas 2.0+)
                new_data = pd.DataFrame([{
                    "rating": stars,
                    "review": review_text,
                    "summary": ai_result.get('summary', 'N/A'),
                    "action": ai_result.get('action', 'N/A'),
                    "reply": ai_result.get('reply', 'Thank you!'),
                    "timestamp": pd.Timestamp.now()
                }])
                
                # 3. Append safely using concat
                try:
                    existing_data = pd.read_csv(DB_FILE)
                    # FIX: Using concat instead of append
                    updated_data = pd.concat([existing_data, new_data], ignore_index=True)
                    updated_data.to_csv(DB_FILE, index=False)
                    
                    st.success("✅ Review Submitted Successfully!")
                    st.info(f"**Auto-Reply:** {ai_result.get('reply')}")
                except Exception as e:
                    st.error(f"Error saving data: {e}")

# --- ADMIN DASHBOARD ---
elif page == "Admin Dashboard":
    st.title("📊 Admin Feedback Console")
    
    if os.path.exists(DB_FILE):
        try:
            df = pd.read_csv(DB_FILE)
            
            # Metrics
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Reviews", len(df))
            avg = df['rating'].mean() if not df.empty else 0
            col2.metric("Average Rating", f"{avg:.1f} ⭐")
            col3.metric("Negative Reviews", len(df[df['rating'] < 3]) if not df.empty else 0)
            
            st.divider()
            st.subheader("Live Feed")
            
            if not df.empty:
                # Sort newest first
                if 'timestamp' in df.columns:
                    df = df.sort_values(by='timestamp', ascending=False)
                
                for i, row in df.iterrows():
                    with st.expander(f"{row['rating']}⭐: {str(row['review'])[:40]}..."):
                        st.write(f"**Full Review:** {row['review']}")
                        st.write(f"**AI Summary:** {row['summary']}")
                        st.write(f"**Recommended Action:** {row['action']}")
                        st.caption(f"Time: {row.get('timestamp', '-')}")
            else:
                st.info("No reviews yet.")
                
        except Exception as e:
            st.error(f"Error reading database: {e}")