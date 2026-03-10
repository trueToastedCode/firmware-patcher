FROM ubuntu:22.04

RUN apt-get update && apt-get install -y \
    gcc-arm-linux-gnueabihf \
    binutils-arm-linux-gnueabihf \
    qemu-user \
    qemu-user-static \
    libc6-dev-armhf-cross \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /test
COPY original.s new.s harness.c ./

# Assemble both .s files — must match the linker's profile (armv7-a)
RUN arm-linux-gnueabihf-as \
        -march=armv7-a \
        -mthumb \
        original.s -o original.o

RUN arm-linux-gnueabihf-as \
        -march=armv7-a \
        -mthumb \
        new.s -o new.o

# Compile harness and link — same arch as .o files
RUN arm-linux-gnueabihf-gcc \
        -march=armv7-a \
        -mthumb \
        -mfpu=vfp \
        -static \
        harness.c original.o new.o \
        -o test_clamp

# Run under QEMU ARM userspace emulation
CMD ["qemu-arm-static", "./test_clamp"]
