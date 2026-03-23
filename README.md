# Birthday Streamlit Page

这是一个给邱肇塬的生日祝福网页，使用 `Streamlit` 加载本地 HTML 页面并对外分享。

## 本地运行

```bash
streamlit run birthday_web.py
```

本地访问:

```text
http://localhost:8501
```

## GitHub + Streamlit Cloud 部署

1. 把当前目录推送到一个 GitHub 仓库
2. 打开 Streamlit Community Cloud
3. 选择该 GitHub 仓库
4. Main file path 填 `birthday_web.py`
5. 部署完成后即可得到公开分享链接

## 主要文件

- `birthday_web.py`: Streamlit 入口
- `Happy-birthDay-master/birthdayIndex.html`: 生日网页主体
- `.streamlit/config.toml`: Streamlit 本地运行配置
