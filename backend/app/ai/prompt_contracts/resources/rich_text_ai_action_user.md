{% if action.key == "chat" %}
{{ instruction }}
{% else %}
文档标题: {{ context_title }}

选中的文本:
{{ selected_text }}

光标前的内容:
{{ before_text }}

光标后的内容:
{{ after_text }}

{% if target_lang %}目标语言: {{ target_lang }}
{% endif %}{% if instruction %}用户指令: {{ instruction }}
{% endif %}
请执行“{{ action.label }}”动作，并只输出处理后的编辑器内容。
{% endif %}
