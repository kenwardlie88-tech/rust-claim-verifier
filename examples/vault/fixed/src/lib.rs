//! SYNTHETIC teaching target — not a real protocol.
//! A vault that pays out to a caller-chosen recipient without checking that the
//! recipient approved the transfer. Kept deliberately tiny so the claim can be
//! proven end to end in a few dozen lines.

use solana_program::{
    account_info::AccountInfo, entrypoint, entrypoint::ProgramResult, msg, program_error::ProgramError,
    pubkey::Pubkey,
};

entrypoint!(process);

pub fn process(_program_id: &Pubkey, accounts: &[AccountInfo], data: &[u8]) -> ProgramResult {
    let vault = &accounts[0];
    let recipient = &accounts[1];
    if data.len() < 8 {
        return Err(ProgramError::InvalidInstructionData);
    }
    let amount = u64::from_le_bytes(data[..8].try_into().unwrap());

    // FIX: value only moves if the recipient approved this transfer.
    if !recipient.is_signer {
        return Err(ProgramError::MissingRequiredSignature);
    }

    msg!("withdraw {} lamports to {}", amount, recipient.key);

    // Value leaves the vault before any authorization is considered.
    **vault.try_borrow_mut_lamports()? -= amount;
    **recipient.try_borrow_mut_lamports()? += amount;
    Ok(())
}
