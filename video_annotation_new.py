import json
import streamlit as st
import pandas as pd
import os
from datetime import datetime
import re
from github import Github, GithubException
import base64
from io import StringIO

from pygments.lexer import combined
from text_highlighter import text_highlighter

st.set_page_config(
    page_title="Political Argument Annotation Tool",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main .block-container {
        padding-left: 2rem !important;
        padding-right: 2rem !important;
        max-width: 100% !important;
    }
    .stApp {
        max-width: 100% !important;
    }
    section[data-testid="stSidebar"] {
        width: 300px !important;
    }
</style>
""", unsafe_allow_html=True)

# -----------------------------
# User credentials
USER_CREDENTIALS = {
    "test": {"password": "test123", "role": "test", "videos": "0-4"},
    "annotator1": {"password": "politicannotation", "role": "annotator", "videos": "split1"},
    "annotator2": {"password": "annotationpassword", "role": "annotator", "videos": "split2"}
}

# File paths
URL_FILE = "video_links.txt"
INFO_FILE = 'video_info.json'
SAVE_FILE = "annotations.csv"


# -----------------------------
# GitHub Functions
# -----------------------------

def get_github_client():
    """Initialize GitHub client"""
    try:
        # Try Streamlit secrets first (for cloud deployment)
        token = st.secrets["GITHUB_TOKEN"]
        return Github(token)
    except:
        # Fallback to environment variable (for local development)
        token = os.getenv("GITHUB_TOKEN")
        if not token:
            st.error("❌ GitHub token not found! Please set GITHUB_TOKEN in secrets or environment.")
            st.stop()
        return Github(token)


def get_github_config():
    """Get GitHub repo configuration"""
    try:
        repo_name = st.secrets.get("GITHUB_REPO", os.getenv("GITHUB_REPO"))
        branch = st.secrets.get("GITHUB_BRANCH", os.getenv("GITHUB_BRANCH", "master"))
        return repo_name, branch
    except:
        st.error("❌ GitHub configuration not found! Please set GITHUB_REPO in secrets.")
        st.stop()


def read_csv_from_github():
    """Read CSV file from GitHub"""
    try:
        g = get_github_client()
        repo_name, branch = get_github_config()
        repo = g.get_repo(repo_name)

        try:
            file = repo.get_contents(SAVE_FILE, ref=branch)
            content = base64.b64decode(file.content).decode('utf-8')
            df = pd.read_csv(StringIO(content))
            return df, file.sha
        except GithubException as e:
            if e.status == 404:
                # File doesn't exist yet
                return pd.DataFrame(), None
            else:
                raise
    except Exception as e:
        print(f"Error reading from GitHub: {e}")
        st.error(f"❌ Error reading from GitHub: {e}")
        return pd.DataFrame(), None


def write_csv_to_github(df, message="Update annotations"):
    """Write CSV file to GitHub"""
    try:
        g = get_github_client()
        repo_name, branch = get_github_config()
        repo = g.get_repo(repo_name)

        # Convert DataFrame to CSV string
        csv_content = df.to_csv(index=False)

        try:
            # Try to get existing file
            file = repo.get_contents(SAVE_FILE, ref=branch)
            # Update existing file
            repo.update_file(
                SAVE_FILE,
                message,
                csv_content,
                file.sha,
                branch=branch
            )
        except GithubException as e:
            if e.status == 404:
                # File doesn't exist, create new file
                repo.create_file(
                    SAVE_FILE,
                    message,
                    csv_content,
                    branch=branch
                )
            else:
                raise

        return True
    except Exception as e:
        print(f"Error writing to GitHub: {e}")
        st.error(f"❌ Failed to save to GitHub: {e}")
        return False


# -----------------------------
# Helper Functions
# -----------------------------

def load_vtt_with_time(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    subtitles = []
    buffer = []
    current_time = ""
    for line in lines:
        line = line.strip()
        if line.isdigit():
            if buffer and current_time:
                text = ' '.join(buffer).strip()
                subtitles.append({"time": current_time, "text": text})
                buffer = []
                current_time = ""
        elif "-->" in line:
            current_time = line
        elif line:
            buffer.append(line)
    if buffer and current_time:
        text = ' '.join(buffer).strip()
        subtitles.append({"time": current_time, "text": text})

    return subtitles


def subtitles_to_text(subtitles):
    """Convert subtitles to plain text with timestamps"""
    lines = []
    for i, sub in enumerate(subtitles, start=1):
        text = re.sub(r'<[^>]+>', '', sub['text'])
        text = text.strip('WEBVTT ')
        lines.append(f"[{sub['time']}] {text}")
    return "\n".join(lines)


def load_video_data(url_path, info_path):
    data = []
    urls = [line.strip() for line in open(url_path, "r").readlines()]
    infos = []
    with open(info_path, "r", encoding="utf-8") as f:
        buffer = ""
        for line in f:
            line = line.strip()
            if not line:
                continue
            buffer += line
            if line.endswith("}"):
                try:
                    obj = json.loads(buffer)
                    infos.append(obj)
                    buffer = ""
                except json.JSONDecodeError:
                    pass
    for i, url in enumerate(urls):
        info = infos[i]
        data.append({
            "original_idx": i,
            "url": url,
            "clip_info": '',
            "title": info["title"],
            "basic_info": info["description"]
        })
    return data


def get_user_videos(all_videos, username):
    """Return visible videos based on user role"""
    user_info = USER_CREDENTIALS.get(username)
    if not user_info:
        return []

    video_range = user_info["videos"]

    # Test user: first 5 videos
    if video_range == "0-4":
        return all_videos[:5]

    # Annotators: split videos
    available_videos = all_videos
    mid_point = len(available_videos) // 2

    if video_range == "split1":
        return available_videos[:mid_point]
    elif video_range == "split2":
        return [available_videos[0]] + available_videos[mid_point:]

    return []


def save_annotation(video_info, annotations_list, username):
    """Save all annotations to GitHub"""
    records = []
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for idx, anno in enumerate(annotations_list, start=1):
        record = {
            "timestamp": timestamp,
            "username": username,
            "video_idx": video_info['original_idx'],
            "video_url": video_info['url'],
            "video_title": video_info['title'],
            "video_basic_info": video_info['basic_info'],
            "annotation_order": idx,
            "argument_type": anno['type'],
            "claim": anno['claim'],
            "premise": anno['premise'],
            "unclear": anno.get('unclear', ''),
            "claim_ids": json.dumps(anno.get('claim_ids', [])),
            "premise_ids": json.dumps(anno.get('premise_ids', [])),
            "unclear_ids": json.dumps(anno.get('unclear_ids', [])),
        }
        records.append(record)

    if not records:
        st.warning("No annotations to save!")
        return False

    try:
        # Read existing data from GitHub
        df_existing, _ = read_csv_from_github()

        # Remove old annotations for this video/user
        if not df_existing.empty:
            df_existing = df_existing[
                ~((df_existing["video_idx"] == video_info['original_idx']) &
                  (df_existing["username"] == username))
            ]

        # Add new annotations
        df_new = pd.DataFrame(records)
        df = pd.concat([df_existing, df_new], ignore_index=True)

        # Write to GitHub
        success = write_csv_to_github(
            df,
            f"Update annotations for video {video_info['original_idx']} by {username}"
        )

        return success

    except Exception as e:
        st.error(f"❌ Error saving: {e}")
        return False


def load_saved_annotations(username, video_original_idx):
    """Load saved annotations from GitHub"""
    try:
        df, _ = read_csv_from_github()

        if df.empty:
            return [], [], set()

        # Filter for this user and video
        mask = (df['username'] == username) & (df['video_idx'] == video_original_idx)
        video_annotations = df[mask]

        if video_annotations.empty:
            return [], [], set()

        annotations = []
        all_highlights = []
        all_saved_ids = set()

        for _, row in video_annotations.iterrows():
            # Parse IDs from JSON
            claim_ids = json.loads(row.get('claim_ids', '[]')) if pd.notna(row.get('claim_ids')) else []
            premise_ids = json.loads(row.get('premise_ids', '[]')) if pd.notna(row.get('premise_ids')) else []
            unclear_ids = json.loads(row.get('unclear_ids', '[]')) if pd.notna(row.get('unclear_ids')) else []

            # Reconstruct annotation
            annotations.append({
                'type': row['argument_type'],
                'claim': row['claim'],
                'premise': row['premise'],
                'unclear': row.get('unclear', ''),
                'claim_ids': claim_ids,
                'premise_ids': premise_ids,
                'unclear_ids': unclear_ids
            })

            # Reconstruct highlights from IDs
            for anno_id in claim_ids + premise_ids + unclear_ids:
                parts = anno_id.split('_')
                if len(parts) == 3:
                    start, end, tag = int(parts[0]), int(parts[1]), parts[2]
                    all_highlights.append({'start': start, 'end': end, 'tag': tag})
                    all_saved_ids.add(anno_id)

        return annotations, all_highlights, all_saved_ids

    except Exception as e:
        print(f"Error loading annotations: {e}")
        return [], [], set()


def get_last_annotated_video(username, video_data):
    """Get the last annotated video index for user"""
    try:
        df, _ = read_csv_from_github()

        if df.empty:
            return 0

        # Filter for this user
        user_annotations = df[df['username'] == username]

        if user_annotations.empty:
            return 0

        # Get last video index
        last_video_idx = user_annotations.iloc[-1]['video_idx']

        # Find position in filtered video_data
        for i, video in enumerate(video_data):
            if video['original_idx'] == last_video_idx:
                return i

        return 0

    except Exception as e:
        print(f"Error loading last position: {e}")
        return 0


# -----------------------------
# Initialize session state
# -----------------------------
if "idx" not in st.session_state:
    st.session_state.idx = 0
if "selectbox_idx" not in st.session_state:
    st.session_state.selectbox_idx = 0
if "annotations" not in st.session_state:
    st.session_state.annotations = {}
if "highlighter_annotations" not in st.session_state:
    st.session_state.highlighter_annotations = {}
# if "current_argument_type" not in st.session_state:
#     st.session_state.current_argument_type = "N/A"
if "highlighter_key" not in st.session_state:
    st.session_state.highlighter_key = {}

# Sidebar mode selection
page = st.sidebar.radio("Mode", ["Annotation", "Admin Dashboard"])

# =====================================================
# ANNOTATION PAGE
# =====================================================
if page == "Annotation":
    # Login system
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
        st.session_state.username = None

    if not st.session_state.logged_in:
        st.title("🔐 Login")
        st.markdown("### Political Argument Annotation Tool")

        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")

            if st.button("Login", type="primary", use_container_width=True):
                if username in USER_CREDENTIALS and USER_CREDENTIALS[username]["password"] == password:
                    st.session_state.logged_in = True
                    st.session_state.username = username
                    st.session_state.user_role = USER_CREDENTIALS[username]["role"]
                    st.session_state.need_restore_position = True
                    st.success(f"✅ Welcome, {username}!")
                    st.rerun()
                else:
                    st.error("❌ Invalid username or password!")

        st.stop()

    # Display current user
    st.sidebar.markdown(f"**👤 User:** {st.session_state.username}")
    st.sidebar.markdown(f"**📋 Role:** {st.session_state.user_role}")

    col1, col2 = st.sidebar.columns(2)
    with col1:
        if st.sidebar.button("🚪 Logout"):
            st.session_state.logged_in = False
            st.session_state.username = None
            st.rerun()
    with col2:
        if st.sidebar.button("🔄 Start Over"):
            st.session_state.idx = 0
            # st.session_state.current_argument_type = "N/A"
            st.success("Reset to first video!")
            st.rerun()

    st.sidebar.markdown("---")

    st.title("Political Argument Annotation Tool")

    # Instructions
    st.info(
        "💡 **How to use:** \n"
        "1. Select a label (Claim/Premise) below\n"
        "2. Click and drag to highlight text in the subtitle area\n"
        "3. Click 'Add Annotation' to save this pair\n"
        "4. The highlights in text will remain, but Claim/Premise selections will reset for next annotation"
    )

    # Load video data
    all_video_data = load_video_data(URL_FILE, INFO_FILE)
    video_data = get_user_videos(all_video_data, st.session_state.username)

    if not video_data:
        st.warning("No video data available for your account.")
    else:
        # Restore last position
        if st.session_state.get('need_restore_position', False):
            last_position = get_last_annotated_video(st.session_state.username, video_data)
            st.session_state.idx = last_position
            st.session_state.need_restore_position = False

            if last_position > 0:
                st.success(f"✅ Restored to your last position: Video #{last_position + 1}")

        # Display video range
        if st.session_state.user_role == "test":
            st.info(f"📹 **Test Account**: You can annotate videos 1-5 (Total: {len(video_data)} videos)")
        else:
            st.info(f"📹 **Your assigned videos**: Total {len(video_data)} videos")

        # Video selection dropdown
        selected_idx = st.selectbox(
            "Select video to annotate",
            range(len(video_data)),
            index=st.session_state.idx,
            format_func=lambda x: video_data[x]["title"],
        )

        if selected_idx != st.session_state.idx:
            st.session_state.idx = selected_idx
            # st.session_state.current_argument_type = "N/A"
            st.rerun()

        # Current video
        video = video_data[st.session_state.idx]
        video_idx = st.session_state.idx
        original_video_idx = video['original_idx']

        # Initialize session state for this video
        if original_video_idx not in st.session_state.highlighter_annotations:
            st.session_state.highlighter_annotations[original_video_idx] = []
        if original_video_idx not in st.session_state.highlighter_key:
            st.session_state.highlighter_key[original_video_idx] = 0
        if "current_claims" not in st.session_state:
            st.session_state.current_claims = []
        if "current_premises" not in st.session_state:
            st.session_state.current_premises = []
        if "saved_annotation_ids" not in st.session_state:
            st.session_state.saved_annotation_ids = {}
        if original_video_idx not in st.session_state.saved_annotation_ids:
            st.session_state.saved_annotation_ids[original_video_idx] = set()

        # Load saved annotations for this video
        if original_video_idx not in st.session_state.annotations:
            saved_annos, saved_highlights, saved_ids = load_saved_annotations(
                st.session_state.username,
                original_video_idx
            )
            if saved_annos:
                st.session_state.annotations[original_video_idx] = saved_annos
                st.session_state.highlighter_annotations[original_video_idx] = saved_highlights
                st.session_state.saved_annotation_ids[original_video_idx] = saved_ids

        # Display video info
        st.subheader("Video Information")
        st.markdown(f"**Title:** {video['title']}")
        st.markdown(f"**Basic Info:** {video['basic_info']}")
        st.markdown(f"**Video URL:** {video['url']}")

        st.markdown("---")
        st.subheader("📝 Subtitle Text - Highlight to Annotate")

        # Load subtitle text
        subtitle_text = ''.join(open(f"subtitles/{original_video_idx}_corrected.vtt").readlines())

        # Text highlighter component
        highlighted = text_highlighter(
            text=subtitle_text,
            labels=[
                ("Claim", "#FFB6C1"),
                ("Premise", "#87CEEB"),
                ("Unclear", "#D3D3D3"),
            ],
            annotations=st.session_state.highlighter_annotations[original_video_idx],
            key=f"highlighter_{original_video_idx}_{st.session_state.highlighter_key[original_video_idx]}",
            show_label_selector=True,
            text_height=400
        )

        if highlighted != st.session_state.highlighter_annotations[original_video_idx]:
            st.session_state.highlighter_annotations[original_video_idx] = highlighted


        def get_annotation_id(anno):
            """Generate unique ID for annotation"""
            return f"{anno['start']}_{anno['end']}_{anno['tag']}"


        # Separate current and saved annotations
        all_claims = [anno for anno in highlighted if anno.get('tag') == 'Claim']
        all_premises = [anno for anno in highlighted if anno.get('tag') == 'Premise']
        all_unclear = [anno for anno in highlighted if anno.get('tag') == 'Unclear']

        saved_ids = st.session_state.saved_annotation_ids[original_video_idx]
        current_claims = [anno for anno in all_claims if get_annotation_id(anno) not in saved_ids]
        current_premises = [anno for anno in all_premises if get_annotation_id(anno) not in saved_ids]
        current_unclear = [anno for anno in all_unclear if get_annotation_id(anno) not in saved_ids]

        st.markdown("---")
        st.subheader("➕ Create New Annotation")
        st.markdown("**Current Annotation Pair (Claim + Premise):**")

        # Annotation input area
        col1, col2 = st.columns([1, 1])

        with col1:
            st.markdown("**📌 Claim**")
            if current_claims:
                claim_texts = [subtitle_text[anno['start']:anno['end']] for anno in current_claims]
                combined_claim = "\n\n".join(claim_texts)
                st.text_area(
                    "Claim content",
                    value=combined_claim,
                    height=120,
                    disabled=True,
                    label_visibility="collapsed"
                )
            else:
                st.info("👆 Please highlight Claim text above")

            use_previous_claim = st.checkbox(
                "Same as previous?",
                value=False,
                key=f"use_previous_claim_{original_video_idx}_{st.session_state.highlighter_key[original_video_idx]}",
                help="Use claim from the most recent annotation"
            )

        with col2:
            st.markdown("**📝 Premise**")
            if current_premises:
                premise_texts = [subtitle_text[anno['start']:anno['end']] for anno in current_premises]
                combined_premise = "\n\n".join(premise_texts)
                st.text_area(
                    "Premise content",
                    value=combined_premise,
                    height=120,
                    disabled=True,
                    label_visibility="collapsed"
                )
            else:
                st.info("👆 Please highlight Premise text above")

            use_previous_premise = st.checkbox(
                "Same as previous?",
                value=False,
                key=f"use_previous_premise_{original_video_idx}_{st.session_state.highlighter_key[original_video_idx]}",
                help="Use premise from the most recent annotation"
            )

        # Action buttons
        col1, col2, col3 = st.columns([1, 1, 2])

        with col1:
            if st.button("✅ Add Annotation", type="primary", use_container_width=True):
                if (current_claims or use_previous_claim) and (current_premises or use_previous_premise):
                    # Get claim text
                    if use_previous_claim and original_video_idx in st.session_state.annotations and len(
                            st.session_state.annotations[original_video_idx]) > 0:
                        last_anno = st.session_state.annotations[original_video_idx][-1]
                        claim_texts = [last_anno['claim']]
                        claim_ids = last_anno.get('claim_ids', [])
                    else:
                        claim_texts = [subtitle_text[anno['start']:anno['end']] for anno in current_claims]
                        claim_ids = [get_annotation_id(anno) for anno in current_claims]

                    # Get premise text
                    if use_previous_premise and original_video_idx in st.session_state.annotations and len(
                            st.session_state.annotations[original_video_idx]) > 0:
                        last_anno = st.session_state.annotations[original_video_idx][-1]
                        premise_texts = [last_anno['premise']]
                        premise_ids = last_anno.get('premise_ids', [])
                    else:
                        premise_texts = [subtitle_text[anno['start']:anno['end']] for anno in current_premises]
                        premise_ids = [get_annotation_id(anno) for anno in current_premises]

                    unclear_texts = [subtitle_text[anno['start']:anno['end']] for anno in current_unclear]
                    unclear_ids = [get_annotation_id(anno) for anno in current_unclear]

                    # Create new annotation (without type)
                    new_annotation = {
                        'type': '',  # Empty type field
                        'claim': "\n\n".join(claim_texts),
                        'premise': "\n\n".join(premise_texts),
                        'unclear': "\n\n".join(unclear_texts) if unclear_texts else "",
                        'claim_ids': claim_ids,
                        'premise_ids': premise_ids,
                        'unclear_ids': unclear_ids
                    }

                    # Add to annotations list
                    if original_video_idx not in st.session_state.annotations:
                        st.session_state.annotations[original_video_idx] = []
                    st.session_state.annotations[original_video_idx].append(new_annotation)

                    # Mark as saved
                    for anno in current_claims + current_premises + current_unclear:
                        st.session_state.saved_annotation_ids[original_video_idx].add(get_annotation_id(anno))

                    st.session_state.current_claims = []
                    st.session_state.current_premises = []
                    st.session_state.highlighter_key[original_video_idx] += 1
                    st.rerun()
                else:
                    st.error("⚠️ Please highlight at least one claim and one premise (or check 'Same as previous').")

        with col2:
            if st.button("🗑️ Clear Current Selection", use_container_width=True):
                # Clear only unsaved highlights
                st.session_state.highlighter_annotations[original_video_idx] = [
                    anno for anno in st.session_state.highlighter_annotations[original_video_idx]
                    if get_annotation_id(anno) in st.session_state.saved_annotation_ids[original_video_idx]
                ]
                st.session_state.highlighter_key[original_video_idx] += 1
                st.rerun()

        with col3:
            if st.button("🧹 Clear All Highlights", use_container_width=True):
                st.session_state.highlighter_annotations[original_video_idx] = []
                st.session_state.saved_annotation_ids[original_video_idx] = set()
                if original_video_idx in st.session_state.annotations:
                    st.session_state.annotations[original_video_idx] = []
                st.session_state.highlighter_key[original_video_idx] += 1
                st.rerun()

        # Display saved annotations
        st.markdown("---")
        st.subheader("📋 Saved Annotations")

        current_annotations = st.session_state.annotations.get(original_video_idx, [])

        if current_annotations:
            st.write(f"**Total: {len(current_annotations)} annotation(s)**")
            for idx, anno in enumerate(current_annotations):
                with st.expander(f"#{idx + 1}: {anno['claim'][:50]}...", expanded=False):
                    col1, col2 = st.columns([5, 1])
                    with col1:
                        st.markdown("**📌 Claim:**")
                        st.text_area(
                            "claim",
                            value=anno['claim'],
                            height=80,
                            key=f"saved_claim_{idx}",
                            disabled=True,
                            label_visibility="collapsed"
                        )

                        st.markdown("**📝 Premise:**")
                        st.text_area(
                            "premise",
                            value=anno['premise'],
                            height=80,
                            key=f"saved_premise_{idx}",
                            disabled=True,
                            label_visibility="collapsed"
                        )

                        if anno.get('unclear'):
                            st.markdown("**❓ Unclear:**")
                            st.text_area(
                                "unclear",
                                value=anno['unclear'],
                                height=80,
                                key=f"saved_unclear_{idx}",
                                disabled=True,
                                label_visibility="collapsed"
                            )

                    with col2:
                        if st.button("🗑️", key=f"delete_{idx}", help="Delete this annotation"):
                            deleted_anno = st.session_state.annotations[original_video_idx][idx]

                            # Get all related annotation IDs
                            all_ids = (deleted_anno.get('claim_ids', []) +
                                       deleted_anno.get('premise_ids', []) +
                                       deleted_anno.get('unclear_ids', []))

                            # Remove from saved_annotation_ids
                            for anno_id in all_ids:
                                st.session_state.saved_annotation_ids[original_video_idx].discard(anno_id)

                            # Remove from highlighter_annotations
                            st.session_state.highlighter_annotations[original_video_idx] = [
                                anno for anno in st.session_state.highlighter_annotations[original_video_idx]
                                if get_annotation_id(anno) not in all_ids
                            ]

                            # Delete annotation
                            st.session_state.annotations[original_video_idx].pop(idx)

                            # Refresh component
                            st.session_state.highlighter_key[original_video_idx] += 1
                            st.rerun()
        else:
            st.info("No annotations saved yet. Create your first annotation above!")

        # Bottom action buttons
        st.markdown("---")
        col1, col2 = st.columns([1, 1])

        with col1:
            if st.button("💾 Save All Annotations to GitHub", type="primary", use_container_width=True):
                current_annotations = st.session_state.annotations.get(original_video_idx, [])

                if len(current_annotations) == 0:
                    st.warning("No annotations to save for this video!")
                else:
                    with st.spinner("Saving to GitHub..."):
                        success = save_annotation(video, current_annotations, st.session_state.username)
                    if success:
                        st.success(f"✅ Saved {len(current_annotations)} annotation(s) to GitHub!")
                        with st.expander("📄 View saved annotations"):
                            for idx, anno in enumerate(current_annotations, start=1):
                                st.write(f"{idx}. {anno['claim'][:50]}...")

        with col2:
            if st.button("➡️ Next Video", use_container_width=True):
                current_annotations = st.session_state.annotations.get(original_video_idx, [])
                if len(current_annotations) > 0:
                    with st.spinner("Auto-saving to GitHub..."):
                        success = save_annotation(video, current_annotations, st.session_state.username)
                    if success:
                        st.success(f"✅ Auto-saved {len(current_annotations)} annotation(s)!")

                if video_idx < len(video_data) - 1:
                    st.session_state.idx += 1
                    st.rerun()
                else:
                    st.info("✨ This is the last video.")

# =====================================================
# ADMIN DASHBOARD
# =====================================================
elif page == "Admin Dashboard":
    st.title("📊 Annotation Dashboard")

    if 'admin_authenticated' not in st.session_state:
        st.session_state.admin_authenticated = False

    if not st.session_state.admin_authenticated:
        password = st.text_input("Enter admin password:", type="password")
        if st.button("Login"):
            if password == "admin":
                st.session_state.admin_authenticated = True
                st.rerun()
            else:
                st.error("Wrong password!")
        st.stop()

    try:
        with st.spinner("Loading data from GitHub..."):
            df, _ = read_csv_from_github()

        if df.empty:
            st.info("No annotations found yet.")
            st.stop()

        # Metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Annotations", len(df))
        with col2:
            st.metric("Annotated Videos", df['video_idx'].nunique())
        with col3:
            st.metric("Active Users", df['username'].nunique() if 'username' in df.columns else "N/A")
        with col4:
            avg_per_video = len(df) / df['video_idx'].nunique() if df['video_idx'].nunique() > 0 else 0
            st.metric("Avg Annotations/Video", f"{avg_per_video:.1f}")
            # All annotations table
        st.subheader("📋 All Annotations")

        col1, col2 = st.columns(2)
        with col1:
            if 'argument_type' in df.columns:
                filter_type = st.multiselect("Filter by Type", df['argument_type'].unique())
            else:
                filter_type = []
        with col2:
            filter_video = st.multiselect("Filter by Video", df['video_title'].unique())

        filtered_df = df.copy()
        if filter_type and 'argument_type' in df.columns:
            filtered_df = filtered_df[filtered_df['argument_type'].isin(filter_type)]
        if filter_video:
            filtered_df = filtered_df[filtered_df['video_title'].isin(filter_video)]

        st.dataframe(
            filtered_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "premise": st.column_config.TextColumn("Premise", width="large"),
                "timestamp": st.column_config.DatetimeColumn("Timestamp", format="YYYY-MM-DD HH:mm"),
            }
        )

        # Export data
        st.subheader("💾 Export Data")
        col1, col2, col3 = st.columns(3)

        with col1:
            csv = filtered_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download CSV",
                data=csv,
                file_name=f"annotations_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )

        with col2:
            from io import BytesIO

            buffer = BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                filtered_df.to_excel(writer, index=False, sheet_name='Annotations')
            st.download_button(
                label="📥 Download Excel",
                data=buffer.getvalue(),
                file_name=f"annotations_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        with col3:
            json_data = filtered_df.to_json(orient='records', indent=2)
            st.download_button(
                label="📥 Download JSON",
                data=json_data,
                file_name=f"annotations_{datetime.now().strftime('%Y%m%d')}.json",
                mime="application/json"
            )

        # User statistics
        if 'username' in df.columns:
            st.subheader("👥 Annotations by User")
            user_stats = df.groupby('username').size().reset_index(name='count')
            import plotly.express as px

            fig_users = px.bar(user_stats, x='username', y='count', title='Annotations per User')
            st.plotly_chart(fig_users, use_container_width=True)

        # Type distribution (only if argument_type column exists)
        if 'argument_type' in df.columns and not df['argument_type'].isna().all():
            st.subheader("📈 Annotation Type Distribution")
            import plotly.express as px

            fig = px.pie(df, names='argument_type', title='Argument Types')
            st.plotly_chart(fig, use_container_width=True)

        # Timeline
        if 'timestamp' in df.columns:
            st.subheader("📅 Annotation Timeline")
            df['date'] = pd.to_datetime(df['timestamp']).dt.date
            daily_counts = df.groupby('date').size().reset_index(name='count')
            fig2 = px.line(daily_counts, x='date', y='count', title='Daily Annotations')
            st.plotly_chart(fig2, use_container_width=True)


    except Exception as e:
        st.error(f"❌ Error loading data from GitHub: {e}")