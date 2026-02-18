{%- import 'vars.mu' as v -%}
{% include 'logo.mu' %}
{% include 'header.mu' %}

Filter by name:{{ v.input('query', 25, query) }}{{ v.btn('GO!', ':/page/peers.mu`*') }}``

{% for peer in peers %}
``
>Peer
    Name:   `_{{ peer.name | replace_malformed }}`_
    Addr:   `_`!`[{{ 'lxmf@' + peer.dst }}]`!`_
    Last announce: `_{{ peer.last_announce }}`_ ({{ peer.since_announce }} ago)
    ``
{%- endfor %}

{% include 'pagination.mu' %}