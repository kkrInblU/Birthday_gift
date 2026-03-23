from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components


PAGE_TITLE = "邱肇塬 3 月 24 日生日快乐"
HTML_FILE = Path(__file__).parent / "Happy-birthDay-master" / "birthdayIndex.html"


st.set_page_config(
    page_title=PAGE_TITLE,
    page_icon="🎂",
    layout="wide",
    initial_sidebar_state="collapsed",
)


def load_html() -> str:
    if not HTML_FILE.exists():
        st.error(f"未找到页面文件: {HTML_FILE}")
        st.stop()

    return HTML_FILE.read_text(encoding="utf-8")


def main() -> None:
    st.markdown(
        """
        <style>
        .stApp {
            background: #0f2233;
        }
        header[data-testid="stHeader"] {
            background: transparent;
        }
        .block-container {
            max-width: 100%;
            padding: 0;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    html_content = load_html()
    components.html(html_content, height=4200, scrolling=True)


if __name__ == "__main__":
    main()
