[M] SOLVE/spec  S=3: solver_survey,driver,gen_chain
api: solver_survey.survey() | solver_survey.inventory(actors) | solver_survey.scale_question(objects) | solver_survey.assemble(ans) | driver.classify(obj) | driver.plan(objects) | driver.briefing(objects,tool_caps) | driver.self_check() | gen_chain.frames_for(period_s,fps) | gen_chain.batches_for(n,per) …
rule: T36 T29 T63 T33 T73 T79 T80 T78 T77 T100
uses: SHOT/gen
usedby: SOLVE/check
inner=1  selftest=2/3
