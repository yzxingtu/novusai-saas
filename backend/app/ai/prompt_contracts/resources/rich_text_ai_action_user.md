{% if action.key == "chat" %}
文档标题: {{ context_title }}

选中的文本:
{{ selected_text }}

光标前的内容:
{{ before_text }}

光标后的内容:
{{ after_text }}

用户问题:
{{ instruction }}

请基于上述显式编辑器上下文回答，并给出可复制或可插入正文的写作建议；不要声称已经修改正文。
{% else %}
文档标题: {{ context_title }}

选中的文本:
{{ selected_text }}

光标前的内容:
{{ before_text }}

光标后的内容:
{{ after_text }}

{% if action.supports_target_lang and target_lang %}目标语言: {{ target_lang }}
{% endif %}{% if instruction %}用户指令: {{ instruction }}
{% endif %}
请执行“{{ action.label }}”动作，并只输出处理后的编辑器内容。
{% endif %}
