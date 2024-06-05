from opanai_call import stream_chat
from tqdm import tqdm
#stream_chat(prompt, model = "gpt-4", chat = True)
prompt = """现在你需要根据下面的主题，写出论文标题为“习近平新时代中国特色社会主义经济思想对中国经济发展的路径与实践”一段内容
    论文的主要结构：
        	1. 习近平新时代中国特色社会主义经济思想的理论基础
            2. 习近平经济思想对中国经济发展的路径指引
            3. 习近平经济思想在中国经济实践中的应用与成效
    下面你需要写一段内容
    内容主题：{} 
    要求：
        格式： 论文中的一段文字
        字数：{} 字左右
        内容： 给出引用的内容，在合适的地方加上注脚，注意在合适的地方加上数据，注意你只是写一段内容，不需要每次都总结。
        回复严格按照下面的格式：
        $$$文章内容：
        $$$文章引用：
"""

theme = ["习近平新时代中国特色社会主义经济思想的基本概念和内涵",
         '习近平经济思想的历史渊源和理论构建过程',
         '习近平经济思想与马克思主义、中国特色社会主义理论的关系',
         '对中国经济发展的路径指引和战略部署的分析',
         '对中国经济结构调整、转型升级和创新驱动发展的重要意义',
         '解决中国经济发展中的矛盾和问题的思路和方法',
         '在中国经济实践中的具体应用和落实情况',
         '对供给侧结构性改革、深化改革开放、扩大内需等方面的实践成效的探讨',
         '在国际经济环境变化、推动经济全球化进程中的作用和贡献',
         '挑战与展望',]

words = [300, 400, 300, 500, 500, 500, 500, 500, 500, 500]
print(len(words)==len(theme))
for i in tqdm(range(len(theme))):
    context = stream_chat(prompt.format(theme[i], words[i]), model = "gpt-4", chat = False)
    with open('./paper.txt', 'a', encoding='utf-8') as f:
        f.write(context)
        f.write('\n\n')