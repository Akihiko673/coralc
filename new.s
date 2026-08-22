.text
    .globl _mmap
_mmap:
    push %rbp
    mov %rsp, %rbp
    sub $8, %rsp
.LBB0:
    sub $8, %rsp
    lea (%rsp), %rsi
    mov %rsi, %rcx
    mov %rsi, %rax
    movq %rax, (%rcx)
    sub $8, %rsp
    lea (%rsp), %rdi
    mov %rdi, %rcx
    mov %rsi, %rax
    movq %rax, (%rcx)
    sub $8, %rsp
    lea (%rsp), %rdi
    mov %rdi, %rcx
    mov %rsi, %rax
    movl %eax, (%rcx)
    sub $8, %rsp
    lea (%rsp), %rdi
    mov %rdi, %rcx
    mov %rsi, %rax
    movl %eax, (%rcx)
    sub $8, %rsp
    lea (%rsp), %rdi
    mov %rdi, %rcx
    mov %rsi, %rax
    movl %eax, (%rcx)
    sub $8, %rsp
    lea (%rsp), %rdi
    mov %rdi, %rcx
    mov %rsi, %rax
    movq %rax, (%rcx)
    sub $8, %rsp
    lea (%rsp), %rax
    movq %rax, -8(%rbp)
    movq %2, %%rdi
	movq %3, %%rsi
	movq %4, %%rdx
	movq %5, %%r10
	movq %6, %%r8
	movq %7, %%r9
	syscall
	movq %%rax, %0
	# clobber:rcx ,  r8 ,  r9 ,  r10 ,  r11 ,  memory 
            
    movq -8(%rbp), %rcx
    mov %rsi, %rax
    movq %rax, (%rcx)
    movq -8(%rbp), %rax
    movq (%rax), %rsi
    mov %rsi, %rdi
    mov $0, %rcx
    cmp %rcx, %rdi
    setl %dl
    movzbl %dl, %edx
    movq -8(%rbp), %rax
    movq (%rax), %rsi
    mov $4095, %r8
    neg %r8
    mov %rsi, %r9
    mov %r8, %rcx
    cmp %rcx, %r9
    setge %r9b
    movzbl %r9b, %r9d
    mov %rdi, %rsi
    movzbl %bl, %esi
    mov $0, %ecx
    cmp %rcx, %rsi
    setne %bl
    movzbl %bl, %esi
    mov %r9, %rdi
    movzbl %dl, %edx
    mov $0, %ecx
    cmp %rcx, %rdi
    setne %dl
    movzbl %dl, %edx
    mov %rsi, %r8
    movzbl %r8b, %r8d
    mov %rdi, %rcx
    movzbl %cl, %ecx
    and %rcx, %r8b
    mov %r8, %rax
    movzbl %al, %eax
    test %rax, %rax
    jnz .LBB1
    jmp .LBB2

.LBB1:
    mov $0, %rax
    mov %rbp, %rsp
    pop %rbp
    ret

.LBB2:
    movq -8(%rbp), %rax
    movq (%rax), %rsi
    mov %rsi, %rax
    mov %rax, %rdi
    mov %rdi, %rax
    mov %rbp, %rsp
    pop %rbp
    ret

    .globl main
main:
    push %rbp
    mov %rsp, %rbp
    sub $40, %rsp
.LBB3:
    sub $8, %rsp
    lea (%rsp), %rsi
    mov %rsi, %rcx
    mov $0, %rax
    movq %rax, (%rcx)
    sub $8, %rsp
    lea (%rsp), %rdi
    mov %rdi, %rcx
    mov $7, %rax
    movq %rax, (%rcx)
    sub $8, %rsp
    lea (%rsp), %r8
    mov %r8, %rcx
    mov $3, %rax
    movq %rax, (%rcx)
    sub $8, %rsp
    lea (%rsp), %r9
    mov %r9, %rcx
    mov $34, %rax
    movq %rax, (%rcx)
    sub $8, %rsp
    lea (%rsp), %r10
    mov $1, %r11
    neg %r11
    mov %r10, %rcx
    mov %r11, %rax
    movq %rax, (%rcx)
    mov %rsi, %rax
    movq (%rax), %rax
    movq %rax, -8(%rbp)
    mov %rdi, %rax
    movq (%rax), %rax
    movq %rax, -16(%rbp)
    mov %r8, %rax
    movl (%rax), %rax
    movq %rax, -24(%rbp)
    mov %r9, %rax
    movl (%rax), %rax
    movq %rax, -32(%rbp)
    mov %r10, %rax
    movl (%rax), %rax
    movq %rax, -40(%rbp)
    sub $8, %rsp
    movq -8(%rbp), %rax
    push %rax
    movq -16(%rbp), %rax
    push %rax
    movq -24(%rbp), %rax
    push %rax
    movq -32(%rbp), %rax
    push %rax
    movq -40(%rbp), %rax
    push %rax
    mov $0, %rax
    push %rax
    pop %r9
    pop %r8
    pop %rcx
    pop %rdx
    pop %rsi
    pop %rdi
    call _mmap
    mov %rax, %rsi
    add $8, %rsp
    mov $0, %rax
    mov %rbp, %rsp
    pop %rbp
    ret