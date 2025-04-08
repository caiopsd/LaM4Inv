import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import numpy as np

# Modelos e dados extraídos da descrição
models = ['gpt-4o', 'gpt-4o-mini', 'o1-mini', 'deepseek-reasoner', 'None']

# Solutions Found
solutions_found_total = [46, 25, 31, 8, 27]
solutions_found_by_model = [37, 21, 28, 8, 0]

# Average Runtime (segundos)
avg_runtime = [1.63, 6.70, 68.20, 267.97, 0.00]

# Average Repeated Fails
avg_repeated_fails = [0.00, 3.16, 23.77, 34.38, 0.00]

# Average Counter Examples
avg_counter_examples = [1.15, 6.72, 23.00, 20.75, 0.00]

# ---------- Gráfico 1: Solutions Found ----------
x = np.arange(len(models))
width = 0.35

fig, ax = plt.subplots()
bar1 = ax.bar(x - width/2, solutions_found_total, width, label='Solutions Found')
bar2 = ax.bar(x + width/2, solutions_found_by_model, width, label='Solutions Found by Model')

ax.set_ylabel('Count')
ax.set_xlabel('Model')
ax.set_title('Solutions Found by Model')
ax.set_xticks(x)
ax.set_xticklabels(models)
ax.legend()

for bar in bar1 + bar2:
    height = bar.get_height()
    ax.annotate(f'{int(height)}',
                xy=(bar.get_x() + bar.get_width() / 2, height),
                xytext=(0, 3),
                textcoords="offset points",
                ha='center', va='bottom')

plt.tight_layout()
plt.savefig('solutions_found.png')
plt.close()


# ---------- Gráfico 2: Average Runtime ----------
fig, ax = plt.subplots()
bars = ax.bar(models, avg_runtime)
ax.set_ylabel('Average Runtime (seconds)')
ax.set_xlabel('Model')
ax.set_title('Average Runtime by Model')

for bar in bars:
    height = bar.get_height()
    ax.annotate(f'{height:.2f}',
                xy=(bar.get_x() + bar.get_width() / 2, height),
                xytext=(0, 3),
                textcoords="offset points",
                ha='center', va='bottom')

plt.tight_layout()
plt.savefig('average_runtime.png')
plt.close()


# ---------- Gráfico 3: Average Repeated Fails ----------
fig, ax = plt.subplots()
bars = ax.bar(models, avg_repeated_fails)
ax.set_ylabel('Average Repeated Fails')
ax.set_xlabel('Model')
ax.set_title('Average Repeated Fails by Model')

for bar in bars:
    height = bar.get_height()
    ax.annotate(f'{height:.2f}',
                xy=(bar.get_x() + bar.get_width() / 2, height),
                xytext=(0, 3),
                textcoords="offset points",
                ha='center', va='bottom')

plt.tight_layout()
plt.savefig('average_repeated_fails.png')
plt.close()


# ---------- Gráfico 4: Average Counter Examples ----------
fig, ax = plt.subplots()
bars = ax.bar(models, avg_counter_examples)
ax.set_ylabel('Average Counter Examples')
ax.set_xlabel('Model')
ax.set_title('Average Counter Examples by Model')

for bar in bars:
    height = bar.get_height()
    ax.annotate(f'{height:.2f}',
                xy=(bar.get_x() + bar.get_width() / 2, height),
                xytext=(0, 3),
                textcoords="offset points",
                ha='center', va='bottom')

plt.tight_layout()
plt.savefig('average_counter_examples.png')
plt.close()
