#!c=0
{% import 'vars.mu' as v -%}

`c`B{{ v.red }}

`!`_You are not Identified`_`!

`b
-~
`B{{ v.gray }}
`a

`!Identification is required for this request`!

Try to add this node to "Trusted" and check "Identify when connecting"

`b
-~

`c{{ v.btn('Return', ':/page/index.mu', v.red) }}
