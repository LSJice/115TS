# (file_list, expected_category)
# file_list 模拟分享根目录下的文件名样本
SAMPLES = [
    # 电视剧：S01E01 / 第N集 / EP01
    (["Game.of.Thrones.S01E01.1080p.mkv", "Game.of.Thrones.S01E02.mkv"], "电视剧"),
    (["某剧.第03集.WEB-DL.mp4"], "电视剧"),
    (["Anime.Series.EP12.mkv"], "电视剧"),  # EP 走电视剧（动漫也是 TV 类型）
    # 电影：单一视频文件，年份在括号里
    (["Avatar.2009.2160p.UHD.mkv"], "电影"),
    (["The.Dark.Knight.2008.mkv"], "电影"),
    # 动漫：日文片名 / 番剧 / 国创 / 漫
    (["鬼灭之刃.第二季.合集.mkv"], "动漫"),
    (["进击的巨人.S01E01.mp4"], "动漫"),  # 兼容：含 S01E01 但中文番名 → 动漫
    # 综艺：综艺/选秀/真人秀
    (["向往的生活.第N期.mp4", "某综艺.2024暑期版.mp4"], "综艺"),
    # 学习：教程/课程/TTC/Coursera/PDF/PPT
    (["Python进阶教程.第01讲.mp4"], "学习"),
    (["machinelearning-lecture-01.pdf"], "学习"),
    # 未命中：未知
    (["random-file.bin"], "_未分类"),
]
