# Portfolio Manager Service
This service interacts with the Portfolio Manager contract to manage a user's portfolio by making decisions and placing buy and sell transactions accordingly.

## Deployment Details
- Safe and Service have been deployed to Gnosis Tenderly Fork.
- Components and Agent have been minted to Ethereum Tenderly Fork.
- Portfolio Manager Contract Address: 0x797971c6f8034ae377c6ebe8edce59ea19e089eb
- Test Token: 0x0937ebb510ff99f7371ae4bcf6980c630777b0f6

## Overview
The Portfolio Manager contract tracks the percentage of tokens a user wants to maintain in their portfolio. For testing purposes, custom ERC-20 tokens have been deployed. The service queries the contract to check the percentage deviation for a particular token and decides how to balance the portfolio based on this information.

## Current Logic
### Rebalancing Rules
- Rebalancing rules are stored on IPFS and can be retrieved to make informed decisions. Although these rules have not yet been used in the current code, they provide a foundation for implementing more sophisticated rebalancing strategies in the future.
### Deviation Check
- Positive Deviation : The service decides to sell the token.
  - It calls a function in the Portfolio Manager contract, transferring the token from the Gnosis Safe to the seller's address.
- Negative Deviation: The service decides to buy the token.
  - It calls a function in the Portfolio Manager contract, transferring the token from the buyer to the Gnosis Safe.

### Transaction Workflow
- #### Sell Transaction:
  1. An approval transaction is made (Gnosis Safe must approve the Portfolio Manager contract to transfer tokens from the Gnosis Safe to another address).
  2. A sell transaction is prepared.
  3. Both transactions are bundled into a multisend transaction.
- #### Buy Transaction:
  1. A single contract call is made to the Portfolio Manager contract to buy the token.

### Future Enhancements
- Implementing complex logic in the service to calculate the amount needed for portfolio rebalancing considering external factors as well.
- Handling multiple tokens within the portfolio.

This service ensures efficient portfolio management by dynamically adjusting the token allocations based on predefined percentage targets.
