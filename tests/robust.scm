; 鲁棒性自查：深递归与边界表达式。每行注释是期望输出。
; 说明：实测本机可支撑约 3 万层 Scheme 递归（超过时干净报错退出，不会崩溃进程），
; 验收用例的递归规模（如 (sum-to 100)）远小于此，这里留了很大的余量。

(define (down n) (if (= n 0) 0 (down (- n 1))))
(down 20000)                    ; → 0
(define (up n acc) (if (= n 0) acc (up (- n 1) (+ acc 1))))
(up 20000 0)                    ; → 20000
(define (deep-list n) (if (= n 0) '() (cons n (deep-list (- n 1)))))
(length (deep-list 20000))      ; → 20000

; --- 边界：空参数、省略分支（结果为「无值」，不打印）---
(cond (#f))
(if #f 1)
(and)                           ; → #t
(or)                            ; → #f
(begin)
(list)                          ; → ()
(let () 42)                     ; → 42
(begin 1)                       ; → 1

; --- 边界：点对写法与嵌套引用 ---
'(a . b)                        ; → (a . b)
'()                             ; → ()
''z                             ; → (quote z)
'(1 (2 (3)))                    ; → (1 (2 (3)))
(eq? '() '())                   ; → #t
(equal? '(1 (2) 3) '(1 (2) 3))  ; → #t

; --- 边界：整数商与浮点除法（spec §5：整数相除得整数商）---
(/ 1 3)                         ; → 0    整数相除得整数商
(/ 3.0 2)                       ; → 1.5  含浮点则做浮点除法
(expt 2 3)                      ; → 8
(expt 2 0)                      ; → 1
(abs (- 0 0))                   ; → 0
(append '(1) '(2) '(3))         ; → (1 2 3)
(append '())                    ; → ()
(car (cdr '(a b c)))            ; → b

; --- 边界：零参数 lambda、混合布尔 ---
((lambda () 'zero-arg))         ; → zero-arg
(if (and #t (or #f 5)) 'mixed 'no)  ; → mixed
(display "")                    ; （打印空字符串，不换行）
(newline)
(display "done")                ; 打印 done
(newline)
