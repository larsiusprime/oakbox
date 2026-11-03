/** The box's frame (SPEC D21): light oak stiles down the window's sides (grain running down) and a rail along its
 * bottom (grain across), mitred at the bottom corners; the lid (OakBand) is its top piece. Pinned to the window's
 * edges, so it stretches with it, no script; drawn over the page but never in the way (no pointer events). */
export function OakFrame() {
  return (
    <div className="rim" aria-hidden="true">
      <div className="rim-l" />
      <div className="rim-r" />
      <div className="rim-b" />
      <div className="rim-jl" />
      <div className="rim-jr" />
      <div className="rim-in" />
      <div className="rim-out" />
    </div>
  );
}
