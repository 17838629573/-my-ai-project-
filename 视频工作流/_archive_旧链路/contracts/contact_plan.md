[S] contact_plan @ATOM/phys  d0  in=0  gen:contract_gen
does: X_g / X_e / X_f 双人与多人接触约束。
api: solve_contact, self_check
const: JOINTS, CONTACT_TOL, DEFAULT_THRESHOLD
impl: self_check → solve_contact
why : IMPROVE_contact_plan.md
