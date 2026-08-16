The Two-Level Segregated Fit (TLSF) is a dynamic memory allocation algorithm designed to provide bounded, constant-time $\mathcal{O}(1)$ performance for allocation and deallocation operations. It is widely used in embedded systems, real-time operating systems (RTOS), and performance-critical game engines due to its deterministic speed and low memory fragmentation. [1, 2, 3] 
## How the TLSF Algorithm Works
Instead of searching through a single massive linked list to find a free block of memory, TLSF divides memory into a two-level hierarchical structure of segregated free lists. [1, 3] 
1. First-Level Segregation (FLI)
Memory block sizes are grouped by powers of two. For example, bin 0 is for 1 to 3 bytes, bin 1 is for 4 to 7 bytes, bin 2 is for 8 to 15 bytes, and so on. This isolates the general size magnitude of the request. [3, 4] 
2. Second-Level Segregation (SLI)
Because grouping strictly by powers of two leaves large gaps (e.g., a 65-byte request might be forced to take a 128-byte block), TLSF subdivides each major bin into smaller, equally sized "sub-bins". For example, the 64 to 127 byte bin might be divided into four SLI sub-bins. [2, 3, 4] 
3. Bitmask Operations
To achieve $\mathcal{O}(1)$ speed, TLSF maintains a bitmap indicating which sub-bins contain free blocks. When a malloc or free occurs, the hardware-optimized bit-scan instruction (like ffs or clz in x86/ARM) evaluates the bitmask to instantly jump to the correct free list. [2, 5, 6] 
## Key Advantages

* Bounded WCET: The Worst-Case Execution Time is completely independent of the size of the heap or the number of allocated blocks, making it highly deterministic. [2, 7, 8] 
* Low Fragmentation: By rounding up to the nearest sub-bin, TLSF acts as a "good-fit" (close to best-fit) allocator, keeping memory waste typically under 15%. [2, 6] 
* Low Overhead: The management structure and block headers impose very small memory footprints (often just 4 bytes per block). [6, 9] 

## Implementations to Explore
You can inspect or use TLSF in your projects via several well-documented open-source libraries:

* Check out the [Matt Conte TLSF Repository](https://github.com/mattconte/tlsf) for an optimized C/C++ implementation.
* Review how the algorithm handles BSD ports on the [Sysprog21 tlsf-bsd Repository](https://github.com/sysprog21/tlsf-bsd).
* Read an in-depth breakdown of writing TLSF from scratch on [Ayush Dixit's Medium Blog](https://medium.com/@ayush_dixit/building-a-memory-allocator-from-scratch-why-tlsf-is-the-real-deal-8b29987520a2). [5, 10] 

If you are evaluating memory algorithms for a specific project, let me know:

* What is your target platform or language (e.g., C, C++, embedded, desktop)?
* Are you looking for a static pool implementation or dynamic pool growth? [11] 


[1] [https://ieeexplore.ieee.org](https://ieeexplore.ieee.org/document/1311009/)
[2] [https://www.gii.upv.es](http://www.gii.upv.es/tlsf/)
[3] [https://www.zhihu.com](https://www.zhihu.com/en/answer/155303060)
[4] [https://arthurvasseur.fr](https://arthurvasseur.fr/blog/vkd-memory-management/)
[5] [https://medium.com](https://medium.com/@ayush_dixit/building-a-memory-allocator-from-scratch-why-tlsf-is-the-real-deal-8b29987520a2)
[6] [https://ricefields.me](https://ricefields.me/2024/04/20/tlsf-allocator.html)
[7] [https://www.cs.purdue.edu](https://www.cs.purdue.edu/homes/spa/courses/cs381/h5.pdf)
[8] [https://github.com](https://github.com/sysprog21/tlsf-bsd)
[9] [https://github.com](https://github.com/RT-Thread-packages/tlsf)
[10] [https://github.com](https://github.com/mattconte/tlsf)
[11] [https://github.com](https://github.com/sysprog21/tlsf-bsd)

To understand the Two-Level Segregated Fit (TLSF) allocator, it helps to look closely at its structure, how it finds memory instantly, and how it handles fragmentation.
## The Core Problem It Solves
Traditional memory allocators (like a basic first-fit or best-fit allocator) have to loop through a linked list of free blocks to find one big enough. If your program has thousands of free blocks, this loop takes a long time. [1, 2] 
TLSF eliminates the loop entirely. It uses arrays and bitmasks so the CPU can calculate exactly where a matching free block is in just a few instructions. [3, 4, 5] 
------------------------------
## 1. The Two-Level Grid Structure
Think of TLSF as a giant grid of buckets containing free memory blocks.

* First Level (Rows): Grouped by powers of two ($2^n$).
* Row 4 holds blocks from 16 to 31 bytes.
   * Row 5 holds blocks from 32 to 63 bytes.
   * Row 6 holds blocks from 64 to 127 bytes. [6] 
* Second Level (Columns): Each row is split into a fixed number of equal columns (usually 4, 8, or 16). If Row 6 (64 to 127 bytes) is split into 4 columns:
* Col 0 holds blocks from 64 to 79 bytes.
   * Col 1 holds blocks from 80 to 95 bytes.
   * Col 2 holds blocks from 96 to 111 bytes.
   * Col 3 holds blocks from 112 to 127 bytes.

Every column in this grid points to a linked list of free memory blocks that fit that exact size range. [7, 8] 
------------------------------
## 2. How Allocation (Malloc) Works in O(1) Time
When you request a block of memory—for example, 90 bytes:

   1. Calculate Grid Position: TLSF does quick math on the number 90 to find the right row and column. 90 falls into Row 6, Column 1 (80 to 95 bytes).
   2. Check the Bitmask: TLSF looks at a single integer variable (a bitmask) where each bit represents a column. If the bit is 1, there is a free block. If it is 0, that column is empty. [9, 10] 
   3. Find the Next Free Block: If Column 1 is empty, TLSF uses a hardware instruction (like clz for Count Leading Zeros) to find the very next 1 bit in the mask. Let's say Column 2 has a 1.
   4. Grab and Split: TLSF jumps directly to Column 2, takes the first free block from that list, carves out your 90 bytes, and puts the remaining leftover memory back into the correct grid piece.

Because it uses bit operations and math instead of loops, this process takes the exact same amount of time every single time. [11, 12] 
------------------------------
## 3. How Deallocation (Free) Works
When you free a piece of memory, TLSF must prevent memory from breaking into tiny, useless pieces (fragmentation). [13, 14] 

   1. Look Left and Right: Every memory block has a header that points to its physical neighbors in memory. TLSF checks if the block immediately before it or after it is also free. [15, 16, 17] 
   2. Merge (Coalescing): If a neighbor is free, TLSF merges them into one larger block. [18, 19] 
   3. Insert into Grid: TLSF calculates the new size of the merged block, finds the correct Row and Column in the grid, inserts the block at the head of that list, and flips the bitmask bit to 1. [20] 

------------------------------
## Why is this ideal for Real-Time Systems?
In a self-driving car, a medical device, or a high-frequency trading application, you cannot have a memory allocation take 1 microsecond one time and 500 microseconds the next time. TLSF guarantees a Worst-Case Execution Time (WCET) that is small and entirely predictable, ensuring the system never misses a critical deadline. [21, 22, 23] 
To help apply this to your project, could you tell me:

* Are you trying to write your own custom allocator, or are you looking to integrate an existing library?
* What specific performance issues or constraints are you currently trying to solve?


[1] [https://github.com](https://github.com/sysprog21/tlsf-bsd)
[2] [https://ricefields.me](https://ricefields.me/2024/04/20/tlsf-allocator.html)
[3] [https://medium.com](https://medium.com/@ayush_dixit/building-a-memory-allocator-from-scratch-why-tlsf-is-the-real-deal-8b29987520a2)
[4] [https://www.researchgate.net](https://www.researchgate.net/publication/4080369_TLSF_A_new_dynamic_memory_allocator_for_real-time_systems)
[5] [https://www.gii.upv.es](http://www.gii.upv.es/tlsf/files/papers/tlsf_desc.pdf)
[6] [https://arthurvasseur.fr](https://arthurvasseur.fr/blog/vkd-memory-management/)
[7] [https://www.mdpi.com](https://www.mdpi.com/2076-3417/13/18/10297)
[8] [https://github.com](https://github.com/sysprog21/tlsf-bsd)
[9] [https://cscie28.dce.harvard.edu](https://cscie28.dce.harvard.edu/~dce-lib215/lectures/lect04/6_Extras/filesystems/filesystems1.html)
[10] [https://flylib.com](https://flylib.com/books/en/3.275.1.39/3/)
[11] [https://medium.com](https://medium.com/@andrew_johnson_4/malloc-algorithms-memory-management-in-lm-5531cde74bc8)
[12] [https://techtalk.intersec.com](https://techtalk.intersec.com/2013/10/memory-part-4-intersecs-custom-allocators/)
[13] [https://byjus.com](https://byjus.com/gate/difference-between-internal-and-external-fragmentation/)
[14] [https://levelup.gitconnected.com](https://levelup.gitconnected.com/malloc-from-scratch-dbc1bc23dfde)
[15] [https://dl.acm.org](https://dl.acm.org/doi/10.1145/3689773)
[16] [https://www.andrew.cmu.edu](https://www.andrew.cmu.edu/course/15-310/applications/ln/lecture26.html)
[17] [https://opencoursehub.cs.sfu.ca](https://opencoursehub.cs.sfu.ca/cmpt201/grav/labs/lab5-mem-allocator)
[18] [https://cs4157.github.io](https://cs4157.github.io/www/2024-1/lect/02-memory-1.html)
[19] [https://phoenixnap.com](https://phoenixnap.com/glossary/worst-fit-allocation)
[20] [https://heap-exploitation.dhavalkapil.com](https://heap-exploitation.dhavalkapil.com/attacks/first_fit)
[21] [https://scispace.com](https://scispace.com/pdf/tlsf-a-new-dynamic-memory-allocator-for-real-time-systems-xaoagk29f4.pdf)
[22] [https://www.gii.upv.es](http://www.gii.upv.es/tlsf/)
[23] [https://blog.devgenius.io](https://blog.devgenius.io/types-of-heap-memory-in-embedded-systems-oses-rtos-linux-kernel-complete-overview-8369c652b170)

