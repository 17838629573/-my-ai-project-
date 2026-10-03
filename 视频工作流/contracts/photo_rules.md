# photo_rules ·红 景别/角度/运动三轴+人体比例+关节禁忌+剪辑梯度
史:notes/photo_rules.md

接口: BODY, JOINTS, SHOT_TYPES(EWS/WS/FS/MFS/MS/MCU/CU/ECU), ANGLES,
      MOVEMENTS, body_pixels(shot,H), ground_y, validate_shot, validate_sequence
headroom: EWS15-22｜WS15-20｜FS10-15｜MFS/MS10-12｜MCU8-12｜CU5-8｜ECU0-5
守恒: headroom+body_frac+footroom=1.0，footroom派生，禁止三者各自手填
