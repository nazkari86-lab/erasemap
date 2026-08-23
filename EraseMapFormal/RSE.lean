namespace EraSeMap.RSE

/-- Reflexive-transitive reachability under a registered or real transition relation. -/
inductive Reachable (step : α → α → Prop) (initial : α) : α → Prop
  | refl : Reachable step initial initial
  | tail {current next : α} :
      Reachable step initial current → step current next → Reachable step initial next

/-- Locally safe registered transitions preserve erasure over their entire reachable closure. -/
theorem registered_reachable_safe
    (residual : α → Prop)
    (registeredStep : α → α → Prop)
    (localSound : ∀ current next, ¬ residual current → registeredStep current next →
      ¬ residual next)
    {initial state : α}
    (initialSafe : ¬ residual initial)
    (reachable : Reachable registeredStep initial state) :
    ¬ residual state := by
  induction reachable with
  | refl => exact initialSafe
  | tail prior transition inductionHypothesis =>
      exact localSound _ _ inductionHypothesis transition

/--
If every real data-bearing transition is covered by the registered semantics, local registered
soundness lifts a snapshot-safe state to a real temporal erasure invariant.
-/
theorem observed_coverage_lifts_to_real_safety
    (residual : α → Prop)
    (realStep registeredStep : α → α → Prop)
    (coverage : ∀ current next, realStep current next → registeredStep current next)
    (localSound : ∀ current next, ¬ residual current → registeredStep current next →
      ¬ residual next)
    {initial state : α}
    (initialSafe : ¬ residual initial)
    (reachable : Reachable realStep initial state) :
    ¬ residual state := by
  induction reachable with
  | refl => exact initialSafe
  | tail prior transition inductionHypothesis =>
      exact localSound _ _ inductionHypothesis (coverage _ _ transition)

def hiddenResidual : Bool → Prop := fun state => state = true

def noRegisteredStep : Bool → Bool → Prop := fun _ _ => False

def hiddenRealStep : Bool → Bool → Prop := fun current next =>
  current = false ∧ next = true

/-- A checked boundary example: local registered soundness is insufficient without coverage. -/
theorem missing_coverage_allows_regeneration :
    (¬ hiddenResidual false) ∧
    (∀ current next, ¬ hiddenResidual current → noRegisteredStep current next →
      ¬ hiddenResidual next) ∧
    Reachable hiddenRealStep false true ∧ hiddenResidual true := by
  refine ⟨by simp [hiddenResidual], ?_, ?_, by simp [hiddenResidual]⟩
  · intro current next currentSafe impossible
    contradiction
  · exact Reachable.tail Reachable.refl ⟨rfl, rfl⟩

end EraSeMap.RSE
