#!/bin/sh

echo "更新代码"
git reset --hard origin/master
git pull

echo "编译国际化文件"
pybabel extract -F babel.cfg -o messages.pot .
pybabel update -i messages.pot -d translations
pybabel compile -d translations

echo "开始打包"
rm -rf dist
pyinstaller v2-ui.spec

echo "进行压缩"
tar zcvf ./dist/v2-ui.tar.gz ./dist/v2-ui