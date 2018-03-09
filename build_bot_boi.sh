find . -path '*/.*' -prune -o -type f -print | zip ../botboi.zip -@
echo 'A new build should exist one directory up now (../botboi.zip)'
