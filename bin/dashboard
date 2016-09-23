#!/bin/bash

TPL="dashboard_files/dashboard.html.in"
OUT="dashboard.html"
if which openqa-review >/dev/null 2>&1 ; then
	OPENQA_REVIEW="openqa-review"
else
	OPENQA_REVIEW="./openqa_review/openqa_review.py"
fi

cache=$(mktemp -d)

GLOBAL_PARAMS="--host https://openqa.suse.de/ --no-empty-sections -R $@"

closed_html=$($OPENQA_REVIEW $GLOBAL_PARAMS --save --save-dir="$cache" -f closed | sed 's/^#\s/#### /' | markdown)
unassigned_html=$($OPENQA_REVIEW $GLOBAL_PARAMS --load --load-dir="$cache" -f unassigned | sed 's/^#\s/#### /' | markdown)

sed '/TPL_OPENQA_CONTENT/q' $TPL | head -n -1 > $OUT
cat >> $OUT <<EOF
<div class="panel panel-default" id="closed_box">
    <div class="panel-heading" style="font-weight: bold;">
        Closed Bugs
    </div>
    <div class="panel-body">
		${closed_html}
    </div>
</div>

<div class="panel panel-default" id="unassigned_box">
    <div class="panel-heading" style="font-weight: bold;">
        Unassigned Bugs
    </div>
    <div class="panel-body">
		${unassigned_html}
    </div>
</div>
EOF

sed '1,/TPL_OPENQA_CONTENT/d' $TPL >> $OUT

rm -r "$cache"
