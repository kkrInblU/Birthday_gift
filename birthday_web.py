import streamlit as st
import time
import random

# 设置页面配置
st.set_page_config(page_title="🎂 生日快乐！", page_icon="🎉", layout="centered")

# 自定义 CSS 样式，让文字更好看
st.markdown("""
    <style>
    .main {
        background-color: #f0f2f6;
    }
    .stButton>button {
        width: 100%;
        border-radius: 20px;
        height: 3em;
        background-color: #ff4b4b;
        color: white;
    }
    h1 {
        color: #ff4b4b;
        text-align: center;
    }
    .blessing-text {
        font-size: 20px;
        line-height: 1.6;
        text-align: center;
        color: #31333F;
    }
    </style>
    """, unsafe_allow_html=True)

def main():
    # --- 寿星名字 ---
    friend_name = "寿星名字" # 记得改成真实名字
    
    st.title(f"✨ {friend_name}，生日快乐！ ✨")
    
    # 顶部装饰图片或动画
    st.image("https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExNHJndXp6Nm9qZ3p6Nm9qZ3p6Nm9qZ3p6Nm9qZ3p6Nm9qZ3p6JmVwPXYxX2ludGVybmFsX2dpZl9ieV9pZCZjdD1n/LROZBXf8K9JcWkUvXW/giphy.gif", use_column_width=True)

    st.write("---")

    # 互动环节：点击开启惊喜
    if st.button("🎁 点击开启你的生日盲盒 🎁"):
        # 满屏气球特效 (Streamlit 内置神技)
        st.balloons()
        
        # 逐行显示祝福语
        with st.container():
            st.markdown(f"### 💌 给你的特别寄语：")
            messages = [
                f"嘿，{friend_name}！",
                "祝你在新的一岁里：",
                "🚀 代码一把过，逻辑全跑通！",
                "💰 钱包鼓鼓，好运连连！",
                "🍔 在汉溪长隆吃得开心，玩得尽兴！",
                "🎮 麻将把把胡，运气挡不住！",
                "🎂 ★ HAPPY BIRTHDAY ★"
            ]
            
            for msg in messages:
                st.markdown(f"<p class='blessing-text'>{msg}</p>", unsafe_allow_html=True)
                time.sleep(0.5)
        
        # 烟花特效 (需安装额外库，这里用雪花代替)
        st.snow()
        
        # 底部随机小彩蛋
        st.info("💡 提示：这是一个由 Trae AI 协助生成的专属生日补丁 v2.0")

    # 侧边栏：5人组名单
    with st.sidebar:
        st.header("🎂 汉溪长隆·5人组")
        st.write("寿星 👸")
        st.write("朋友 A 🙋‍♂️")
        st.write("朋友 B 🙋‍♀️")
        st.write("朋友 C 🙋‍♂️")
        st.write("你自己 👨‍💻")
        st.write("---")
        st.write("📍 位置：汉溪长隆民宿")

if __name__ == "__main__":
    main()