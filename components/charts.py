import json, os, re
from matplotlib import pyplot as plt
from streamlit import session_state
from streamlit.components.v1 import html

# web friendly theming
TEMPLATE = """
<canvas id="appleChart" style="width:100%;height:400px;"></canvas>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-datalabels@2"></script>
    <script>
    const canvas = document.getElementById('appleChart');
    const ctx = canvas.getContext('2d');
    const grad = ctx.createLinearGradient(0,0,ctx.canvas.width,0);
    grad.addColorStop(0, '#3399FF');
    grad.addColorStop(1, '#FF3E96');
    const unit = {unit};

    Chart.register(ChartDataLabels);

    const config = {{
        type: 'bar',
        data: {{
            labels: {labels},
            datasets: [
                {{
                    data: {values},
                    backgroundColor: grad,
                    barThickness: 9,
                    categoryPercentage: 0.5,
                    barPercentage: 1.0,
                    datalabels: {{
                        align: 'end',
                        anchor: 'end',
                        offset: 4,
                        formatter: v => v.toFixed(0) + unit,
                        color: function(ctx) {{
                            const all = ctx.dataset.data;
                            const maxVal = Math.max(...all);
                            return ctx.dataset.data[ctx.dataIndex] === maxVal ? grad : 'white';
                        }},
                        font: {{ size: 18, weight: '700' }}
                    }}
                }}
            ]
        }},
        options: {{  
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            scales: {{
                x: {{
                    display: false,
                    max: {max_val},
                }},
                y: {{
                    ticks: {{
                        color: 'white',
                        font: {{ size: 18, weight: '700', family: 'Montserrat, sans-serif' }}
                    }},
                    grid: {{ display: false }},
                    border: {{ display: false }}
                }}
            }},
            plugins: {{
                legend: {{ display: false }},
                datalabels: {{}}
            }},
            animation: {{
                duration: 1500,
                easing: 'easeOutCubic'
            }},
            layout: {{
                padding: {{ top: 10, right: 60, bottom: 0, left: 0}}
            }}
        }},
        plugins: [ChartDataLabels]
    }};

    // Only create the chart when canvas scrolls into view
    const observer = new IntersectionObserver((entries, obs) => {{
      entries.forEach(entry => {{
        if (entry.isIntersecting) {{
          new Chart(ctx, config);
          obs.unobserve(canvas);
        }}
      }});
    }}, {{ threshold: 0.1 }});

    observer.observe(canvas);
    </script>
"""

def web_chart(labels: list[str], values: list[float],
              height: int | None = None, width: int | None = None,
              sort: str = 'none', unit: str = '%'):
    """Renders the Chart.js template with given labels & values."""

    # Default height and width values
    if height is None:
        height = 300 + 25 * len(labels)
    if width is None:
        width = 700

    # Modify labels so it's not too long to fit in chart
    labels = [label[:28] + "..." if len(label) > 28 else label for label in labels]
    unit = unit[:4] # in case someone parses a stupidly large unit in: the chart can't handle it

    # Optional sorting
    if sort.lower() == 'ascending':
        paired = sorted(zip(labels, values), key=lambda x: x[1])
        labels, values = zip(*paired) if paired else ([], [])
    elif sort.lower() == 'descending':
        paired = sorted(zip(labels, values), key=lambda x: x[1], reverse=True)
        labels, values = zip(*paired) if paired else ([], [])

    # otherwise sort == 'none' leaves original order
    # Serialize lists to JSON literals
    labels_json = json.dumps(labels)
    values_json = json.dumps(values)
    unit_json = json.dumps(unit)
    max_val = max(values) if values else 0
    chart_html = TEMPLATE.format(
        labels=labels_json,
        values=values_json,
        max_val=max_val,
        unit=unit_json
    )
    # Display in Streamlit
    html(chart_html, height=height, width=width)

# matplotlib theming function -- if we ever need to utilize matplotlib
def plt_boxplot(y, x=None, orientation='horizontal'):
    # shorten x labels to 28 characters
    x = [i[:31]+"..." if len(i) > 31 else i for i in x]
    
    # Dark theme
    plt.style.use('dark_background')  # built-in dark style for dark-mode apps  [oai_citation:4‡Matplotlib](https://matplotlib.org/stable/gallery/style_sheets/dark_background.html?utm_source=chatgpt.com)

    # Modern sans-serif font
    plt.rcParams['font.family'] = 'sans-serif'
    plt.rcParams['font.sans-serif'] = ['Montserrat', 'Arial', 'Helvetica', 'DejaVu Sans']

    # Create transparent figure and axes
    fig, ax = plt.subplots(figsize=(6, 4), facecolor='none')
    fig.patch.set_alpha(0)              # figure background transparent  [oai_citation:5‡Stack Overflow](https://stackoverflow.com/questions/4581504/how-to-set-opacity-of-background-colour-of-graph-with-matplotlib?utm_source=chatgpt.com)
    ax.set_facecolor('none')            # axes background transparent

    # Plot boxplot
    ax.boxplot(y, labels=x, patch_artist=True,
               orientation=orientation,
               boxprops=dict(facecolor='#3399FF', edgecolor='white'),
               medianprops=dict(color='white'),
               whiskerprops=dict(color='white'),
               capprops=dict(color='white'),
               flierprops=dict(markerfacecolor='white', markeredgecolor='white'))

    # make bold
    for tick in ax.get_xticklabels():
        tick.set_fontweight('bold')
    for tick in ax.get_yticklabels():
        tick.set_fontweight('bold')

    # Remove grid and extraneous spines
    ax.grid(False)
    ax.spines['top'].set_visible(False)    # hide top spine  [oai_citation:6‡Stack Overflow](https://stackoverflow.com/questions/925024/how-can-i-remove-the-top-and-right-axis?utm_source=chatgpt.com)
    ax.spines['right'].set_visible(False)  # hide right spine  [oai_citation:7‡Stack Overflow](https://stackoverflow.com/questions/925024/how-can-i-remove-the-top-and-right-axis?utm_source=chatgpt.com)

    # Style remaining axes and ticks for visibility
    ax.spines['bottom'].set_color('white')
    ax.spines['left'].set_color('white')
    ax.tick_params(colors='white', which='both')  # tick labels in white

    return fig, ax