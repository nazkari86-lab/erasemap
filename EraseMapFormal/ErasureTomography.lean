namespace EraSeMap.ErasureTomography

/-- A bounded tomography support is the ordered list of active catalogue mechanisms. -/
abbrev Support (Mechanism : Type) := List Mechanism

/--
The formal v1 contract uses the confirmatory protocol's zero-error observation model. The
executable Python certificate separately checks all bounded supports and reports ambiguity when
two supports share an outcome.
-/
structure Problem (Mechanism : Type) where
  candidates : List (Support Mechanism)
  encode : Support Mechanism → List Bool
  observation : List Bool
  actual : Support Mechanism
  catalogueClosed : actual ∈ candidates
  observationSound : encode actual = observation
  separated : ∀ left, left ∈ candidates → ∀ right, right ∈ candidates →
    encode left = encode right → left = right

def Admissible (problem : Problem Mechanism) (support : Support Mechanism) : Prop :=
  support ∈ problem.candidates ∧ problem.encode support = problem.observation

/-- The real bounded support is admissible when catalogue closure and observation soundness hold. -/
theorem actual_is_admissible (problem : Problem Mechanism) :
    Admissible problem problem.actual := by
  exact ⟨problem.catalogueClosed, problem.observationSound⟩

/--
If every listed support has a distinct observation signature, no different listed support can
decode the same zero-error recurrence vector.
-/
theorem unique_decode_of_separated
    (problem : Problem Mechanism) {candidate : Support Mechanism}
    (candidateAdmissible : Admissible problem candidate) :
    candidate = problem.actual := by
  exact problem.separated candidate candidateAdmissible.1 problem.actual
    problem.catalogueClosed (candidateAdmissible.2.trans problem.observationSound.symm)

/-- Equal signatures for different supports exhibit an observation with two valid explanations. -/
theorem ambiguous_without_separation
    (encode : Support Mechanism → List Bool)
    {left right : Support Mechanism}
    (different : left ≠ right)
    (sameOutcome : encode left = encode right) :
    ∃ observation, encode left = observation ∧ encode right = observation ∧ left ≠ right := by
  exact ⟨encode left, rfl, sameOutcome.symm, different⟩

/--
ET-to-TRE composition deliberately guarantees only the mechanisms in the localized bounded list.
It contains no quantification over arbitrary unlisted infrastructure.
-/
structure StabilizedProblem (Mechanism Control : Type) where
  localized : List Mechanism
  selected : Control
  safe : Control → Mechanism → Prop
  controlsSound : ∀ mechanism, mechanism ∈ localized → safe selected mechanism

theorem localized_controls_safe_for_listed_mechanisms
    (problem : StabilizedProblem Mechanism Control) :
    ∀ mechanism, mechanism ∈ problem.localized → problem.safe problem.selected mechanism := by
  exact problem.controlsSound

end EraSeMap.ErasureTomography
