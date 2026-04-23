document.addEventListener("DOMContentLoaded", () => {
    if (window.dashboardData) {
        const attackChartDom = document.getElementById("attackChart");
        const trendChartDom = document.getElementById("trendChart");

        if (attackChartDom) {
            const attackChart = echarts.init(attackChartDom);
            const attackDistribution = Object.entries(window.dashboardData.attackDistribution)
                .map(([name, value]) => ({ name, value }));
            attackChart.setOption({
                tooltip: { trigger: "item" },
                series: [
                    {
                        type: "pie",
                        radius: ["45%", "72%"],
                        itemStyle: {
                            borderRadius: 10,
                            borderColor: "#fff",
                            borderWidth: 2,
                        },
                        label: { show: true },
                        data: attackDistribution,
                    },
                ],
            });
        }

        if (trendChartDom) {
            const trendChart = echarts.init(trendChartDom);
            trendChart.setOption({
                tooltip: { trigger: "axis" },
                xAxis: {
                    type: "category",
                    data: window.dashboardData.trendLabels,
                },
                yAxis: { type: "value" },
                series: [
                    {
                        data: window.dashboardData.trendValues,
                        type: "line",
                        smooth: true,
                        areaStyle: {},
                        color: "#b45309",
                    },
                ],
            });
        }
    }
});
