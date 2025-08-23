{%- import 'vars.mu' as v -%}
{% include 'logo.mu' %}
{% include 'header.mu' %}

Filter by name:{{ v.input('query', 25, query) }}{{ v.btn('GO!', ':/page/peers.mu`*') }}``

{% for peer in peers %}
``
>Peer
    Name:   `_{{ peer.name | replace_malformed }}`_
    Addr:   `_`!`[{{ 'lxmf@' + peer.dst }}]`!`_
    Online: `_{{ peer.last_online }}`_ ({{ peer.since_online }} ago)
    ``
{%- endfor %}