namespace EraSeMap.PCUG.Boundary

inductive RealPath where
  | hiddenReplica

inductive RegisteredPath where
  | declaredStore

inductive Channel where
  | storage

def realActive : RealPath → Prop := fun _ => True
def pathClosed : RegisteredPath → Prop := fun _ => True
def represents : RealPath → RegisteredPath → Prop := fun _ _ => False
def channelPasses : Channel → Prop := fun _ => True
def channelHolds : Channel → Prop := fun _ => False

/-- Without topology completeness, every registered path can close while a hidden residual exists. -/
theorem unregistered_residual_counterexample :
    (∀ registered, pathClosed registered) ∧ (∃ real, realActive real) := by
  exact ⟨fun _ => trivial, ⟨RealPath.hiddenReplica, trivial⟩⟩

/-- Without channel soundness, a declared pass need not imply the real obligation. -/
theorem unsound_channel_counterexample :
    (∀ channel, channelPasses channel) ∧ (∃ channel, ¬ channelHolds channel) := by
  exact ⟨fun _ => trivial, ⟨Channel.storage, fun impossible => impossible⟩⟩

end EraSeMap.PCUG.Boundary
