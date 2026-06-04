(function () {
    var dataEl = document.getElementById('home-chart-data');
    if (!dataEl || typeof echarts === 'undefined') return;

    var data = JSON.parse(dataEl.textContent);
    var newPostsEl = document.getElementById('home-chart-new-posts');
    var categoryEl = document.getElementById('home-chart-categories');
    if (!newPostsEl || !categoryEl) return;

    var newPostsChart = echarts.init(newPostsEl);
    var categoryChart = echarts.init(categoryEl);

    function colors() {
        var style = getComputedStyle(document.documentElement);
        return {
            text: style.getPropertyValue('--text').trim() || '#1d1d1f',
            muted: style.getPropertyValue('--text-muted').trim() || '#86868b',
            divider: style.getPropertyValue('--gray-divider').trim() || '#e8e8ed',
            blue: style.getPropertyValue('--blue').trim() || '#0071e3',
        };
    }

    function render() {
        var c = colors();
        var palette = ['#0071e3', '#34c759', '#ff9500', '#af52de', '#ff2d55', '#5ac8fa', '#ffcc00'];
        var daily = data.daily_new_posts || [];
        var categories = data.categories.length
            ? data.categories
            : [{ name: '暂无菜品', value: 1, itemStyle: { color: c.divider } }];

        newPostsChart.setOption({
            color: [c.blue],
            tooltip: {
                trigger: 'axis',
                formatter: function (params) {
                    var p = params[0];
                    return p.name + '<br/>新增 ' + p.value + ' 道菜品';
                },
            },
            grid: { left: 40, right: 16, top: 28, bottom: 28 },
            xAxis: {
                type: 'category',
                boundaryGap: false,
                data: daily.map(function (d) { return d.label; }),
                axisLine: { lineStyle: { color: c.divider } },
                axisLabel: { color: c.muted },
            },
            yAxis: {
                type: 'value',
                minInterval: 1,
                splitLine: { lineStyle: { color: c.divider } },
                axisLabel: { color: c.muted },
            },
            series: [{
                name: '新增菜品',
                type: 'line',
                smooth: true,
                symbol: 'circle',
                symbolSize: 8,
                lineStyle: { width: 3 },
                areaStyle: {
                    color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                        { offset: 0, color: 'rgba(0, 113, 227, 0.28)' },
                        { offset: 1, color: 'rgba(0, 113, 227, 0.02)' },
                    ]),
                },
                data: daily.map(function (d) { return d.count; }),
            }],
        }, true);

        categoryChart.setOption({
            color: palette,
            tooltip: {
                trigger: 'item',
                formatter: function (p) {
                    if (p.name === '暂无菜品') return '还没有分享菜品';
                    return p.name + '<br/>' + p.value + ' 道菜品 (' + p.percent + '%)';
                },
            },
            legend: {
                type: 'scroll',
                bottom: 0,
                textStyle: { color: c.muted, fontSize: 12 },
            },
            series: [{
                type: 'pie',
                radius: ['40%', '68%'],
                center: ['50%', '44%'],
                avoidLabelOverlap: true,
                itemStyle: { borderRadius: 6, borderColor: c.divider, borderWidth: 2 },
                label: { color: c.text, fontSize: 12, formatter: '{b}\n{d}%' },
                data: categories,
            }],
        }, true);
    }

    render();

    window.addEventListener('resize', function () {
        newPostsChart.resize();
        categoryChart.resize();
    });

    document.querySelectorAll('[data-theme-set]').forEach(function (btn) {
        btn.addEventListener('click', function () {
            setTimeout(render, 0);
        });
    });
})();
