# EraSeMap: единый fail-closed алгоритм проверяемого удаления данных и влияния в модели

**Автор:** ____________________
**Организация:** ____________________
**Научный руководитель:** ____________________

## Аннотация

Команда удаления основной записи не гарантирует, что персональные данные перестали использоваться.
Копии могут сохраняться в кэше, индексе, реплике, экспорте или backup; производные — в
биометрическом шаблоне и векторе; влияние — в обученной модели. Более того, удалённый объект может
появиться снова после restore, sync, rebuild или повторного развёртывания модели.

В работе представлен EraSeMap — один алгоритм из трёх стадий: **FIND** находит зарегистрированные и
ограниченно скрытые пути; **ERASE** выбирает минимальный достаточный набор физических действий и
machine unlearning; **PROVE** выполняет temporal replay и разрешает сертификат только после
прохождения всех обязательных каналов. Алгоритм возвращает `COMPLETE_WITHIN_ENVELOPE`, `INCOMPLETE`
или `UNVERIFIED`; отсутствие доказательств никогда не считается успехом.

В frozen transfer на 60 случаях EraSeMap дал 0 ложных `COMPLETE` против 5 у полного typed-аудита и
45 у native service status. Активный поиск bounded recovery-графа потребовал 7 проб против 13 у
frozen random и 49 у exhaustive; greedy получил те же 7. В 20 парных опытах с реальными локальными
процессами targeted plan был геометрически в 17,64 раза быстрее rebuild-all и записал на 94,62%
меньше байтов. Temporal проверка обнаружила 30/30 латентных рисков и после controls дала 0/30
возвратов. Exact solvers совпали с exhaustive oracles в 3072/3072 и 16 384/16 384 конфигурациях.
Быстрые unlearning-кандидаты на Qwen2.5-1.5B не прошли все frozen gates, поэтому exact retraining
сохранён как безопасный fallback. Результаты относятся к зарегистрированным topology и transition
envelopes; production FaceID/eGov и независимый hidden challenge не заявляются.

**Ключевые слова:** проверяемое удаление, machine unlearning, data lineage, temporal replay,
биометрия, fail-closed, сертификат удаления.

## 1. Введение

Право на удаление и внутренние политики организаций требуют устранить данные одного человека. На
практике одно событие порождает цепочку артефактов: исходную запись, нормализованный профиль,
биометрический template, поисковый vector, cache, журнал, export, backup и параметры модели. Каждый
компонент может вернуть успешную локальную квитанцию, хотя система в целом продолжает использовать
человека.

Существующие направления решают части задачи. Data lineage описывает происхождение данных [9].
Machine unlearning уменьшает влияние обучающих примеров [1, 2], а verification-of-unlearning
оценивает доказательность результата [3–8]. Политики удаления и патенты рассматривают lineage,
backup и receipts [10–12, 16, 18]. Однако локальное доказательство одной части нельзя автоматически
перенести на физические производные, модель и будущую регенерацию одновременно.

Исследовательский вопрос работы:

> Как выдать один проверяемый subject-level вердикт удаления, который одновременно учитывает
> физические копии, производные, влияние в модели и зарегистрированные будущие пути восстановления?

Вклад работы:

1. единый трёхстадийный fail-closed алгоритм FIND–ERASE–PROVE;
2. формальная типизированная модель физического, производного и model-channel evidence;
3. exact minimum-cost selection с контрпримером при невозможности удаления;
4. temporal replay, запрещающий сертификат при возможной регенерации;
5. обязательное сравнение machine unlearning с exact retraining и сохранение отрицательных
   результатов;
6. воспроизводимая многоуровневая оценка на bounded graphs, реальных локальных процессах, stock
   services, face data и открытой модели Qwen2.5-1.5B.

## 2. Предшествующие работы и граница новизны

EraSeMap не заявляет изобретение lineage graphs, set cover, active testing, temporal model checking,
machine unlearning или цифровой подписи. Новизна формулируется уже и проверяемее: это композиция
всех обязательств в одном subject-level decision rule, где ни одна локальная квитанция не может
самостоятельно создать положительный verdict.

В отличие от обычного lineage-аудита, важен не только тип узла, но и пригодный путь от субъекта к
активному артефакту. В отличие от model-only unlearning, удаление влияния в модели не закрывает
backup, cache или vector index. В отличие от snapshot testing, текущая пустота не доказывает, что
restore не вернёт объект. В отличие от универсального обещания, `COMPLETE_WITHIN_ENVELOPE` явно
ограничивает гарантию зарегистрированной системой.

## 3. Модель системы

### 3.1 Типизированный граф

Пусть система представлена графом

```text
G = (V, E, τ, s),
```

где `V` — артефакты и сервисы, `E` — операции происхождения или восстановления, `τ` — типы узлов и
рёбер, `s` — subject binding. Для субъекта `u` множество пригодных остаточных путей обозначается
`Rᵤ(G)`. Путь считается активным, если его конечный артефакт может хранить, выдавать, распознавать
или восстанавливать информацию о `u`.

Обязательные каналы `Cᵤ` включают:

- `physical`: исходные и резервные физические артефакты;
- `derivative`: templates, embeddings, indexes и exports;
- `model`: влияние в обученной модели;
- `privacy`: заранее объявленные privacy-proxy проверки;
- `utility`: качество для retained subjects/tasks;
- `temporal`: отсутствие возврата после будущих операций;
- `coverage`: достаточность зарегистрированной instrumentation.

Каждый verifier возвращает `PASS`, `FAIL` или `UNKNOWN`.

### 3.2 Три вердикта

```text
COMPLETE_WITHIN_ENVELOPE:
    Rᵤ(G) = ∅ и каждый обязательный канал PASS,
    discovery evidence валиден, temporal replay безопасен.

INCOMPLETE:
    существует конкретный активный или регенерируемый путь.

UNVERIFIED:
    ни остаток, ни полное удаление нельзя доказать доступным evidence.
```

Трёхзначность не является интерфейсной деталью: она исключает превращение отсутствующего evidence в
ложный успех.

## 4. Единый алгоритм EraSeMap

### 4.1 FIND

FIND сначала replay-проверяет зарегистрированный граф. Если карта может быть неполной, adapter
выполняет безопасные синтетические пробы: разрешает определённые recovery-операции и наблюдает,
какой тестовый субъект, где и когда появился. После каждой пробы остаются только графы, совместимые
с trace. Стадия возвращает единственный граф, полный observable path class, `OUT_OF_HYPOTHESIS` или
`UNVERIFIED`.

Пусть `H` — конечный version space графов, а `Obs(q,h)` — trace эксперимента `q` на гипотезе `h`.
После наблюдения `o`:

```text
H' = {h ∈ H : Obs(q,h) = o}.
```

Exact one-step minimax выбирает допустимую пробу, минимизирующую размер худшего следующего класса с
детерминированным tie-break. Это локальная гарантия, а не оптимальность всего adaptive tree.

### 4.2 ERASE

Пусть `A` — конечный каталог разрешённых действий, `c(a) ≥ 0` — стоимость, `Apply(G,B)` — система
после подмножества `B ⊆ A`. План допустим, если все действия разрешены и replay закрывает каждый
активный path и обязательный channel. Выбирается

```text
B* = arg min  Σ c(a)
              a∈B
     subject to Feasible(B) = true.
```

При равенстве используется стабильный lexicographic tie-break. Если полного permitted plan нет,
выдаётся `INCOMPLETE` или `UNVERIFIED`, но не частичная квитанция.

Model branch находится внутри ERASE. Candidate unlearning сравнивается с exact retraining по
forgetting, retained utility, privacy proxy, deletion-matched distance и recurrence after reload.
Общий model pass равен конъюнкции frozen gates. Провал одного gate означает fallback к exact
retraining либо незавершённый model channel.

### 4.3 PROVE

Пусть `q₀` — состояние после ERASE, а `δ` — зарегистрированные будущие переходы. Требуется, чтобы ни
одно достижимое состояние не содержало пригодный residual:

```text
Safe(u) ⇔ ∀q ∈ Reach(q₀, δ): Residual(u,q) = false.
```

Если replay находит recurrence witness, PROVE возвращает `INCOMPLETE` и кратчайший контрпример. Если
transition coverage неизвестен, результат `UNVERIFIED`. Только безопасный replay разрешает
certificate-ready status.

### 4.4 Общая формула

Пусть `P` — закрытие physical/model paths, `D` — валидное discovery evidence, `T` — temporal safety:

```text
COMPLETE_WITHIN_ENVELOPE ⇔ P ∧ D ∧ T.
```

## 5. Формальные свойства

Lean-проект проверяет четыре условных свойства без `sorryAx`:

1. replayed completion исключает представленные residual paths при полноте topology и sound local
   verifiers;
2. exact finite selector выбирает feasible plan не дороже любого другого listed feasible plan;
3. observed transition coverage переносит snapshot absence на все reachable registered states;
4. exact temporal selector безопасен и минимален при явной feasibility-soundness obligation.

Отдельные checked counterexamples показывают, что скрытый residual возможен без topology coverage и
что passed channel бессмыслен без soundness. Python implementation отдельно сравнивается с
exhaustive oracles; Lean не доказывает Python semantics, adapters или реальную полноту организации.

## 6. Реализация

Публичный Python entry point `run_erasemap` возвращает три stage results и общий verdict. Service
adapters отделены от pure verifier, поэтому алгоритм не выполняет неразрешённые network или
destructive calls. Evidence bundles связываются hashes и, где предусмотрено протоколом, Ed25519
signatures. CLI создаёт offline-verifiable showcase и отчёты.

Внутренние названия PCUG, GhostGraph, CDC, RSE и MSC используются только для трассировки evidence и
formal namespaces. Они не образуют пять конкурирующих пользовательских алгоритмов.

## 7. Методика экспериментов

### 7.1 Основная метрика

Критический риск — false-complete rate:

```text
FCR = false COMPLETE / фактически незавершённые случаи.
```

Дополнительные метрики: probes, action cost, wall time, bytes written, retained loss, recurrence,
oracle mismatches, forgetting, utility и privacy advantage.

### 7.2 Evidence layers

1. Mechanism stress проверяет различие typed-node и channel-aware path semantics.
2. Stock-service transfer использует digest-pinned Keycloak, MLflow и Qdrant на 60 frozen cases.
3. Bounded hidden graphs сравнивают active minimax, greedy, random и exhaustive FIND.
4. Measured multi-service experiment сравнивает targeted ERASE и rebuild-all на real PostgreSQL,
   Redis, Qdrant, encrypted backup и ridge model.
5. Temporal lab проверяет delayed restore, sync, cache/index rebuild и coverage faults.
6. Face experiments проверяют bounded unlearning и retained-user privacy.
7. Qwen–TOFU проверяет adapter-level learned influence на реальной открытой 1.5B model.

Протоколы, seeds, gates и source hashes фиксировались до соответствующих confirmation runs. Failed
results не удаляются и не переписываются.

## 8. Результаты

| Проверка | EraSeMap | Baseline | Интерпретация |
|---|---:|---:|---|
| Stock-service false `COMPLETE` | 0/60 | typed 5/60; native 45/60 | FIND/coverage предотвращает локальную квитанцию |
| Hidden-graph probe budget | 7 | greedy 7; random 13; exhaustive 49 | выигрыш против random/exhaustive, ничья с greedy |
| Exact action conformance | 3072/3072 | exhaustive oracle | 0 mismatches в bounded domain |
| Targeted execution time | 5,67% | rebuild-all 100% | 17,64× geometric speedup |
| Written bytes | 5,38% | rebuild-all 100% | 94,62% reduction |
| Temporal risk detection | 30/30 | snapshot 0/30 | PROVE проверяет более сильный future claim |
| Post-control recurrence | 0/30 | no control 30/30 | registered controls закрыли frozen risks |
| Exact temporal conformance | 16 384/16 384 | exhaustive oracle | 0 mismatches в bounded domain |

Все 20 paired real-process cases сохранили completion и retained data. Frozen transfer также дал 0
retained loss и 0 post-control recurrence.

### 8.1 Model channel

Bounded face experiments дали положительное project-authored evidence, включая preregistered
sequential retained-user privacy gates. Однако это не certified privacy.

Qwen v1 проверил три seeds и завершился `FAIL`: candidate приблизился к exact по части метрик, но не
выполнил одновременно forgetting и world-utility требования. Qwen v2 использовал author-disjoint
development selection и пять untouched confirmation seeds; candidate был быстрее минимум в 30,48
раза и имел нулевую recurrence after reload, но overscrubbing и несколько exact-matching/utility
gates провалились. Итоговый model verdict для fast candidates остаётся incomplete; exact adapter
retraining является reference fallback. Это не ухудшает логику EraSeMap, а демонстрирует её
отказоустойчивость.

## 9. Обсуждение

Главный результат — не универсальное превосходство одного численного метода. EraSeMap связывает
разные evidence types так, чтобы слабая локальная метрика не могла закрыть весь deletion request.
Например, низкий membership score не доказывает удаление backup, а пустой snapshot не доказывает
отсутствие future restore.

Active FIND уменьшает число диагностических проб, но strong greedy baseline получил ничью на frozen
catalogue; эта ничья сохраняется. Targeted ERASE показывает большой systems saving против rebuild-all,
однако на одной локальной машине. PROVE расширяет утверждение во времени, но только при transition
coverage. Таким образом, каждая сильная цифра сопровождается собственной границей.

## 10. Ограничения и угрозы валидности

- Hidden graphs, mappings, faults и execution созданы проектом; accepted external run отсутствует.
- Stock services реальны, но subjects синтетические или публичные, а не customer records.
- Bounded catalogue не покрывает произвольную секретную инфраструктуру.
- Local verifier может быть неверным; signature защищает целостность, но не истинность измерения.
- Performance измерен на одной локальной конфигурации.
- Face privacy experiment не является certified privacy.
- Qwen experiments относятся к adapter influence, а не к удалению из pretraining Qwen.
- Production FaceID, eGov, KYC, bank или government deployment не проводился.

## 11. Этика и ответственное применение

Публичные демонстрации используют synthetic identities или открытые datasets. Active probes должны
быть разрешены владельцем системы, изолированы и не затрагивать retained users. EraSeMap нельзя
использовать для ложного compliance: scope сертификата, UNKNOWN channels и instrumentation gaps
должны оставаться видимыми.

## 12. Воспроизводимость

```bash
python -m venv .venv
.venv/bin/pip install -e '.[dev,real]'
./scripts/reproduce_release.sh core
.venv/bin/erasemap showcase --repo-root . --output outputs/jury-showcase-v1
```

Release gate включает Ruff, strict mypy, pytest с coverage не ниже 90%, build, frozen evidence
verifiers, oracle comparisons и Lean. External hidden challenge имеет отдельный blind handoff;
текущий результат `NOT_COLLECTED`.

## 13. Заключение

EraSeMap превращает удаление данных из локальной команды в один проверяемый процесс. FIND находит
зарегистрированные и bounded hidden paths; ERASE закрывает физические и model branches минимальным
достаточным планом; PROVE проверяет future regeneration и разрешает scoped certificate. Формальные
свойства условны и явно ограничены assumptions; реальные отрицательные ML results сохранены. Такой
дизайн лучше поддерживает честное решение в FaceID/eGov/KYC-подобных системах, но production и
независимость остаются следующими этапами, а не готовыми claims.

## Список литературы

[1] Cao Y., Yang J. Towards Making Systems Forget with Machine Unlearning. IEEE S&P, 2015. DOI: 10.1109/SP.2015.35.

[2] Bourtoule L. et al. Machine Unlearning. IEEE S&P, 2021. arXiv:1912.03817.

[3] Sommer D. M. et al. Towards Probabilistic Verification of Machine Unlearning. arXiv:2003.04247, 2020.

[4] Weng J. et al. Proof of Unlearning: Definitions and Instantiation. arXiv:2210.11334, 2022.

[5] Eisenhofer T. et al. Verifiable and Provably Secure Machine Unlearning. SaTML, 2025.

[6] Chourasia R., Shah N. Forget Unlearning: Towards True Data-Deletion in Machine Learning. ICML, 2023.

[7] Zhang B. et al. Verification of Machine Unlearning is Fragile. ICML, 2024.

[8] Koloskova A. et al. Certified Unlearning for Neural Networks. ICML, 2025.

[9] Lebo T., Sahoo S., McGuinness D., eds. PROV-O: The PROV Ontology. W3C Recommendation, 2013.

[10] US20220414070A1. Tracking Data Lineage and Applying Data Removal to Enforce Data Removal Policies, 2022.

[11] US11120156B2. Privacy Preserving Data Deletion, 2021.

[12] US12456052B2. Systems and Methods for Facilitating Verifiability of ML Model Unlearning, 2025.

[13] NIST SP 800-63A-4. Digital Identity Guidelines: Identity Proofing and Enrollment, 2025.

[14] EraSeMap. Публичный репозиторий и evidence archive, v0.5.0, 2026: https://github.com/nazkari86-lab/erasemap.

[15] Chakraborty V. et al. Meaningful Data Erasure in the Presence of Dependencies. PVLDB 18(10), 2025.

## Приложение A. Обозначения

| Символ | Значение |
|---|---|
| `G=(V,E,τ,s)` | зарегистрированный typed erasure graph |
| `u` | субъект одного deletion request |
| `Rᵤ(G)` | активные остаточные пути субъекта |
| `Cᵤ` | обязательные verifier channels |
| `A` | конечный каталог candidate actions |
| `B*` | минимальный feasible action set |
| `H` | bounded version space recovery graphs |
| `δ` | зарегистрированные будущие переходы |
| `FCR` | false-complete rate |

## Приложение B. Claim–evidence map

| Claim | Evidence | Граница |
|---|---|---|
| Replayed completion условно sound | Lean theorem и counterexamples | зависит от topology/verifier assumptions |
| Exact ERASE минимален | Lean + 3072/3072 oracle matches | finite registered catalogue |
| PROVE temporal-safe | Lean + 16 384/16 384 oracle matches | registered transition coverage |
| FIND уменьшает probe budget | 7 vs 13 random vs 49 exhaustive | finite project-authored catalogue; greedy tie |
| Targeted ERASE дешевле rebuild-all | 17,64× и −94,62% bytes | одна local system, synthetic identities |
| Fast Qwen unlearning успешен | не подтверждено: v1/v2 `FAIL` | exact retraining остаётся fallback |
| External hidden generalization | protocol ready | `NOT_COLLECTED` |
| Production FaceID/eGov | pilot protocol only | не установлено |
