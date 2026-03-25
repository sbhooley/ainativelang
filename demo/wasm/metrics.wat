;; Simple WASM module with utility functions
;; Exports:
;;   - add(i32, i32) -> i32
;;   - lead_score(i32, i32, i32) -> i32  (review_count, rating*100, website_age_days) -> score

(module
  ;; add: (i32, i32) -> i32
  (func $add (param $a i32) (param $b i32) (result i32)
    local.get $a
    local.get $b
    i32.add)
  (export "add" (func $add))

  ;; lead_score: (review_count, rating_x100, website_age_days) -> i32
  ;; score = reviews * rating/100 + age_days (simple heuristic)
  (func $lead_score (param $reviews i32) (param $rating_x100 i32) (param $age_days i32) (result i32)
    (local $rating_score i32)
    ;; rating_score = (reviews * rating_x100) / 100
    local.get $reviews
    local.get $rating_x100
    i32.mul
    i32.const 100
    i32.div_s   ;; signed divide, ok since positive
    local.set $rating_score
    ;; result = rating_score + age_days
    local.get $rating_score
    local.get $age_days
    i32.add)
  (export "lead_score" (func $lead_score))

  ;; overlap_score_f32(q_token_count, d_token_count, inter_count) -> f32
  ;; Matches VectorMemoryAdapter-style: inter / (sqrt(q*d) + 1e-9) with counts as f32.
  (func $overlap_score_f32 (param $q f32) (param $d f32) (param $inter f32) (result f32)
    (f32.div
      (local.get $inter)
      (f32.add
        (f32.sqrt (f32.mul (local.get $q) (local.get $d)))
        (f32.const 1e-9)
      )
    )
  )
  (export "overlap_score_f32" (func $overlap_score_f32))
)
