[S] contact_ik @ATOM/phys  d0  in=0  gen:contract_gen
does: X_h：末端执行器（手/脚）到物体接触点的 IK 约束。
api: solve_two_bone, contact_ik, self_check
const: L1, L2, MAX_EXT
impl: self_check → contact_ik；内部helper 2个
why : IMPROVE_contact_ik.md
