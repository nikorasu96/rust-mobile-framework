#![doc = "Executable composition-root contract for the headless example."]

use std::process::Command;

#[test]
fn mounts_a_declarative_tree_through_the_real_commit_pipeline() {
    let output = match Command::new(env!("CARGO_BIN_EXE_hello-headless")).output() {
        Ok(output) => output,
        Err(error) => unreachable!("example binary is executable: {error}"),
    };

    assert!(output.status.success());
    assert_eq!(output.stdout, b"revision=1 root=1 nodes=2\n");
    assert!(output.stderr.is_empty());
}
