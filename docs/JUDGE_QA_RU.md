# EraSeMap: сложные вопросы жюри

## «В чём новизна, если machine unlearning и data lineage уже существуют?»

Не в отдельных компонентах. Узкая гипотеза — единый subject-scoped fail-closed контракт, который
одновременно охватывает физические производные, request-scoped model influence, обязательные
количественные каналы, replay действий, кратчайший контрпример и минимальную remediation. В работе
отдельно перечислено, что не является новым.

## «Почему typed-node baseline проиграл 75 из 75? Он специально слабый?»

Это node-state baseline, поэтому он по определению не видит неисправный model verifier или replay.
Stress test демонстрирует конкретный механизм добавленной ценности, но не доказывает внешнее
превосходство. На source-locked holdout сильный полный typed baseline связал PCUG 0/100 против
0/100; этот tie открыт в отчёте.

## «Что именно доказал Lean?»

При полной зарегистрированной топологии и sound локальных verifier результат `COMPLETE` исключает
представленные реальные residual paths и закрывает обязательные каналы. Также проверена
оптимальность конечного exhaustive CDC selector. Lean не доказывает, что организация обнаружила
все секретные копии или правильно интегрировала каждый production driver.

## «17,64x — это ускорение FaceID?»

Нет. Это геометрическое среднее для локальной зарегистрированной топологии из PostgreSQL, Redis,
Qdrant, AES-GCM backup и ridge model на синтетических identities. Оно показывает системный выигрыш
targeted exact CDC относительно rebuild-all в этой постановке.

## «Почему не заявляете внедрение в eGov?»

Потому что авторизованного доступа и instrumentation eGov не было. `egov_style` — демонстрационный
adapter общей семантики, а не интеграция. Production claim допускается только после подписанного
организационного pilot manifest.

## «Можно ли подделать proof bundle?»

Подпись защищает целостность, но сама по себе не делает ложное утверждение истинным. Checker
проверяет Ed25519, commitments, replay, пути, каналы и declared verdict. При этом злонамеренный
оператор, скрывший незарегистрированную копию от instrumentation, остаётся вне гарантии.

## «Почему независимость только 7.8?»

Потому что внешний evaluator ещё не прислал independently authored hidden challenge. Код,
подписи и CI повышают readiness, но не независимость. Один валидный внешний PASS по зафиксированной
рубрике поднимет этот показатель до 9.5.

## «Какой отрицательный результат вы получили?»

Первая быстрая MUFAC candidate не прошла retained-utility gate. Safe policy переключилась на exact
retraining. Поздний adaptive v3.2 прошёл неизменённые bounded gates при 1.59x, но считается
method-improvement после exposure, а не новым независимым подтверждением.

## «Что нужно для реального внедрения?»

Авторизованная topology registration, sound drivers для каждого хранилища, trusted key management,
проверка freshness/replay, redacted signed evidence и внешний production pilot как минимум на двух
независимо сохраняемых системах.

## «Разве TRE не решает проблему неполной топологии полностью?»

Нет. TRE гарантирует безопасность только для конечного uncertainty envelope, объявленного до
выбора плана. Если реальная топология находится вне envelope, гарантия не действует. Новое свойство
состоит в том, что один exact-план проходит каждый допустимый сценарий и явно показывает цену
устойчивости, а не в магическом обнаружении неизвестных сервисов.

## «Robust optimization уже существует — где тогда новизна TRE?»

Robust set cover, uncertainty sets и network interdiction не новые и прямо исключены из claim.
Рабочая новизна — проверяемая композиция с subject-scoped temporal erasure: fail-closed coverage,
реальный replay heterogeneous carriers, shortest adversarial regeneration witness, единый exact
control set и robustness premium относительно nominal MSC. Это working contribution, а не
заявление мирового приоритета.

## «Почему nominal MSC провалился 35 из 35 — baseline искусственно ослаблен?»

Nominal MSC не ошибочен: он оптимален для заранее объявленной backup-only топологии и выбирает
дешёвый backup filter. Shifted cases проверяют другой вопрос — что происходит после добавления
пути, которого не было в nominal map. TRE заранее получает конечный envelope и платит на 4
условные единицы больше, чтобы защитить все его варианты. Blanket baseline также защищает их, но
стоит 60 вместо 7.
