namespace EraSeMap.PCUG

/-- Abstract proof obligations connecting a registered PCUG to real residual paths. -/
structure SoundReplay
    (RealPath RegisteredPath Channel : Type)
    (realActive : RealPath → Prop)
    (pathClosed : RegisteredPath → Prop)
    (represents : RealPath → RegisteredPath → Prop)
    (channelHolds : Channel → Prop)
    (channelPasses : Channel → Prop) : Prop where
  topologyComplete : ∀ real, realActive real →
    ∃ registered, represents real registered
  closedPathSound : ∀ real registered,
    represents real registered → pathClosed registered → ¬ realActive real
  channelSound : ∀ channel, channelPasses channel → channelHolds channel

/-- Replayed `COMPLETE` is fail-closed: all registered paths are closed and all channels pass. -/
structure CompleteReplay
    (RegisteredPath Channel : Type)
    (pathClosed : RegisteredPath → Prop)
    (channelPasses : Channel → Prop) : Prop where
  allPathsClosed : ∀ registered, pathClosed registered
  allChannelsPass : ∀ channel, channelPasses channel

/-- A replayed COMPLETE rules out every represented real residual path. -/
theorem replayed_complete_no_real_residual
    {RealPath RegisteredPath Channel : Type}
    {realActive : RealPath → Prop}
    {pathClosed : RegisteredPath → Prop}
    {represents : RealPath → RegisteredPath → Prop}
    {channelHolds : Channel → Prop}
    {channelPasses : Channel → Prop}
    (sound : SoundReplay RealPath RegisteredPath Channel realActive pathClosed
      represents channelHolds channelPasses)
    (complete : CompleteReplay RegisteredPath Channel pathClosed channelPasses) :
    ∀ real, ¬ realActive real := by
  intro real active
  obtain ⟨registered, represented⟩ := sound.topologyComplete real active
  exact sound.closedPathSound real registered represented
    (complete.allPathsClosed registered) active

/-- The same replay also discharges every mandatory channel obligation. -/
theorem replayed_complete_channels_hold
    {RealPath RegisteredPath Channel : Type}
    {realActive : RealPath → Prop}
    {pathClosed : RegisteredPath → Prop}
    {represents : RealPath → RegisteredPath → Prop}
    {channelHolds : Channel → Prop}
    {channelPasses : Channel → Prop}
    (sound : SoundReplay RealPath RegisteredPath Channel realActive pathClosed
      represents channelHolds channelPasses)
    (complete : CompleteReplay RegisteredPath Channel pathClosed channelPasses) :
    ∀ channel, channelHolds channel := by
  intro channel
  exact sound.channelSound channel (complete.allChannelsPass channel)

/-- Combined PCUG soundness result used by the project claim. -/
theorem replayed_complete_sound
    {RealPath RegisteredPath Channel : Type}
    {realActive : RealPath → Prop}
    {pathClosed : RegisteredPath → Prop}
    {represents : RealPath → RegisteredPath → Prop}
    {channelHolds : Channel → Prop}
    {channelPasses : Channel → Prop}
    (sound : SoundReplay RealPath RegisteredPath Channel realActive pathClosed
      represents channelHolds channelPasses)
    (complete : CompleteReplay RegisteredPath Channel pathClosed channelPasses) :
    (∀ real, ¬ realActive real) ∧ (∀ channel, channelHolds channel) := by
  constructor
  · exact replayed_complete_no_real_residual sound complete
  · exact replayed_complete_channels_hold sound complete

end EraSeMap.PCUG
