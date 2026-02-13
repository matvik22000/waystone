{%- import 'vars.mu' as v -%}
{% include 'logo.mu' %}
{% include 'header.mu' %}

Filter by name:{{ v.input('query', 25, query) }}{{ v.btn('GO!', ':/page/nodes.mu`*') }}``
{%- if mentions_for != "" %} || Nodes, that mentioned `_{{ mentions_for }}`_ {% endif %}
{% for node in nodes %}
``
>Node
    Name:   `!`_`[{{ node["name"] }}`{{ node["dst"] }}:/page/index.mu]`_`!
    Owner:  `_`[{{ node.owner[0] | replace_malformed }}`{{ 'lxmf@' + node.owner[1] }}]`_
    Online: `_{{ node.last_online }}`_ ({{ node.since_online }} ago)
    Mentions: `_`[{{ node.citations }}`:/page/nodes.mu`mentions_for={{ node.dst }}]`_
{% endfor %}
{% include 'pagination.mu' -%}
