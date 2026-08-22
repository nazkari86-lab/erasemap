namespace EraSeMap.ExactCDC

/-- Exhaustive minimum-cost selector over a finite, explicitly registered candidate list. -/
def select (feasible : α → Bool) (cost : α → Nat) : List α → Option α
  | [] => none
  | candidate :: rest =>
      match select feasible cost rest with
      | none => if feasible candidate then some candidate else none
      | some incumbent =>
          if feasible candidate && cost candidate ≤ cost incumbent
          then some candidate
          else some incumbent

theorem select_mem
    (feasible : α → Bool) (cost : α → Nat) {candidates : List α} {best : α}
    (selected : select feasible cost candidates = some best) :
    best ∈ candidates := by
  induction candidates generalizing best with
  | nil => simp [select] at selected
  | cons candidate rest ih =>
      simp only [select] at selected
      cases htail : select feasible cost rest with
      | none =>
          simp only [htail] at selected
          split at selected
          · simp_all
          · contradiction
      | some incumbent =>
          simp only [htail] at selected
          split at selected
          · simp_all
          · simp only [Option.some.injEq] at selected
            subst best
            exact List.mem_cons_of_mem candidate (ih htail)

theorem select_feasible
    (feasible : α → Bool) (cost : α → Nat) {candidates : List α} {best : α}
    (selected : select feasible cost candidates = some best) :
    feasible best = true := by
  induction candidates generalizing best with
  | nil => simp [select] at selected
  | cons candidate rest ih =>
      simp only [select] at selected
      cases htail : select feasible cost rest with
      | none =>
          simp only [htail] at selected
          split at selected <;> simp_all
      | some incumbent =>
          simp only [htail] at selected
          split at selected
          · rename_i hchoose
            simp only [Option.some.injEq] at selected
            subst best
            exact (Bool.and_eq_true_iff.mp hchoose).1
          · simp only [Option.some.injEq] at selected
            subst best
            exact ih htail

theorem select_none_no_feasible
    (feasible : α → Bool) (cost : α → Nat) {candidates : List α}
    (selected : select feasible cost candidates = none) :
    ∀ candidate, candidate ∈ candidates → feasible candidate = false := by
  induction candidates with
  | nil => simp
  | cons head rest ih =>
      simp only [select] at selected
      cases htail : select feasible cost rest with
      | none =>
          simp only [htail] at selected
          split at selected
          · contradiction
          · rename_i headNotFeasible
            intro candidate member
            rcases List.mem_cons.mp member with rfl | memberRest
            · cases hvalue : feasible candidate <;> simp_all
            · exact ih htail candidate memberRest
      | some incumbent =>
          simp only [htail] at selected
          split at selected <;> contradiction

theorem select_cost_le
    (feasible : α → Bool) (cost : α → Nat) {candidates : List α} {best other : α}
    (selected : select feasible cost candidates = some best)
    (member : other ∈ candidates)
    (otherFeasible : feasible other = true) :
    cost best ≤ cost other := by
  induction candidates generalizing best with
  | nil => simp at member
  | cons candidate rest ih =>
      simp only [select] at selected
      cases htail : select feasible cost rest with
      | none =>
          simp only [htail] at selected
          split at selected
          next candidateFeasible =>
            simp only [Option.some.injEq] at selected
            subst best
            rcases List.mem_cons.mp member with rfl | memberRest
            · exact Nat.le_refl _
            · have notFeasible := select_none_no_feasible feasible cost htail other memberRest
              simp_all
          next candidateNotFeasible => contradiction
      | some incumbent =>
          simp only [htail] at selected
          split at selected
          next chooseCandidate =>
            simp only [Option.some.injEq] at selected
            subst best
            have candidateCheaper : cost candidate ≤ cost incumbent :=
              of_decide_eq_true (Bool.and_eq_true_iff.mp chooseCandidate).2
            rcases List.mem_cons.mp member with rfl | memberRest
            · exact Nat.le_refl _
            · exact Nat.le_trans candidateCheaper (ih htail memberRest)
          next keepIncumbent =>
            simp only [Option.some.injEq] at selected
            subst best
            rcases List.mem_cons.mp member with rfl | memberRest
            · have notCheaper : ¬ cost other ≤ cost incumbent := by
                intro cheaper
                apply keepIncumbent
                simp [otherFeasible, cheaper]
              exact Nat.le_of_lt (Nat.lt_of_not_ge notCheaper)
            · exact ih htail memberRest

/-- The selector returns a listed feasible candidate with globally minimum cost. -/
theorem selected_is_feasible_minimum
    (feasible : α → Bool) (cost : α → Nat) {candidates : List α} {best : α}
    (selected : select feasible cost candidates = some best) :
    best ∈ candidates ∧ feasible best = true ∧
      ∀ other, other ∈ candidates → feasible other = true → cost best ≤ cost other := by
  exact ⟨select_mem feasible cost selected, select_feasible feasible cost selected,
    fun other member otherFeasible =>
      select_cost_le feasible cost selected member otherFeasible⟩

/-- Returning `none` is equivalent to absence of a feasible listed candidate. -/
theorem select_eq_none_iff
    (feasible : α → Bool) (cost : α → Nat) (candidates : List α) :
    select feasible cost candidates = none ↔
      ∀ candidate, candidate ∈ candidates → feasible candidate = false := by
  constructor
  · exact select_none_no_feasible feasible cost
  · intro noneFeasible
    cases hselected : select feasible cost candidates with
    | none => rfl
    | some best =>
        have member := select_mem feasible cost hselected
        have isFeasible := select_feasible feasible cost hselected
        have isNotFeasible := noneFeasible best member
        simp_all

end EraSeMap.ExactCDC
