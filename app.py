import streamlit as st
import pandas as pd
import google.generativeai as genai
import os
import json

# --- 1. SETUP & SECRETS ---
try:
    # Get key from Streamlit Cloud Secrets
    API_KEY = st.secrets["GOOGLE_API_KEY"]
except FileNotFoundError:
    # If secrets missing, show error
    st.error("⚠️ API Key missing! Please add GOOGLE_API_KEY to your Secrets.")
    st.stop()

# --- 2. CONFIGURATION ---
genai.configure(api_key=API_KEY)

# PRIORITY LIST OF MODELS TO TRY
# If the first one hits a limit, we try the next.
MODEL_FALLBACK_LIST = [
    "models/gemini-2.0-flash",
    "models/gemini-2.0-flash-lite-preview-02-05", 
    "models/gemini-2.5-flash"
]

# --- 3. DATABASE (CSV FILE) ---
DB_FILE = "reviews.csv"

if not os.path.exists(DB_FILE):
    pd.DataFrame(columns=["rating", "review", "summary", "action", "reply", "timestamp"]).to_csv(DB_FILE, index=False)

# --- 4. AI FUNCTIONS (WITH FALLBACK LOGIC) ---
def process_review(review_text, rating):
    prompt = f"""
    You are a helpful customer support AI for Fynd.
    A user just left this {rating}-star review: "{review_text}"
    
    1. Summarize the review in 1 sentence.
    2. Suggest an internal action for the admin (e.g., "Issue Refund", "Send Thank You Note").
    3. Draft a polite, short reply to the user.
    
    Return JSON: {{"summary": "...", "action": "...", "reply": "..."}}
    """
    
    last_error = None
    
    # 🔄 LOOP THROUGH MODELS
    for model_name in MODEL_FALLBACK_LIST:
        try:
            # Initialize the specific model
            model = genai.GenerativeModel(model_name)
            
            # Attempt generation
            response = model.generate_content(prompt)
            
            # Clean and Parse
            clean_text = response.text.replace("```json", "").replace("```", "").strip()
            result = json.loads(clean_text)
            
            # If we get here, it worked! Add a small note about which model was used (optional debug)
            result['model_used'] = model_name 
            return result
            
        except Exception as e:
            # If it fails, capture error and loop to the next model
            last_error = e
            continue 

    # If ALL models fail, show the last error
    st.error(f"⚠️ All AI models failed. Last error: {str(last_error)}")
    return {
        "summary": "System Busy", 
        "action": "Manual Review", 
        "reply": "Thank you for your feedback! (AI currently overloaded)"
    }

# --- 5. UI ---
st.set_page_config(page_title="AI Automated Feedback System", layout="wide")
st.sidebar.title("AI Automated Feedback System")
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
                
                # 2. Create New Row
                new_data = pd.DataFrame([{
                    "rating": stars,
                    "review": review_text,
                    "summary": ai_result.get('summary', 'N/A'),
                    "action": ai_result.get('action', 'N/A'),
                    "reply": ai_result.get('reply', 'Thank you!'),
                    "timestamp": pd.Timestamp.now()
                }])
                
                # 3. Save
                try:
                    existing_data = pd.read_csv(DB_FILE)
                    updated_data = pd.concat([existing_data, new_data], ignore_index=True)
                    updated_data.to_csv(DB_FILE, index=False)
                    
                    st.success("✅ Review Submitted Successfully!")
                    st.info(f"**Auto-Reply:** {ai_result.get('reply')}")
                    
                    # Optional: Show which model worked (Good for testing)
                    if 'model_used' in ai_result:
                        st.caption(f"Processed by: {ai_result['model_used']}")
                        
                except Exception as e:
                    st.error(f"Error saving data: {e}")

# --- ADMIN DASHBOARD ---
elif page == "Admin Dashboard":
    st.title("📊 Admin Feedback Console")
    
    if os.path.exists(DB_FILE):
        try:
            df = pd.read_csv(DB_FILE)
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Reviews", len(df))
            avg = df['rating'].mean() if not df.empty else 0
            col2.metric("Average Rating", f"{avg:.1f} ⭐")
            col3.metric("Negative Reviews", len(df[df['rating'] < 3]) if not df.empty else 0)
            
            st.divider()
            st.subheader("Live Feed")
            
            if not df.empty:
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


