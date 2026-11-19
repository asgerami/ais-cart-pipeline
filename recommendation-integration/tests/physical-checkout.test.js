'use strict';
const assert = require('node:assert/strict');
const handler = require('../../api/recommend');
const field = value => ({status:'observed',value,evidence:'Visible in user screenshot'});
const pipeline = {mode:'live',facts:{merchant:field('Best Buy'),line_items:[{
 name:field('Black+Decker - Small Portable Washer,Portable Washer 0.9 Cu. Ft. with 5 Cycles, Transparent Lid & LED Display - White'),
 quantity:field('1'),line_total:field('$279.99'),term:{status:'unknown',value:null,evidence:''}}],
 subtotal:field('$369.98'),discounts:field('-$20.00'),tax:field('$23.19'),total_due_now:field('$373.17'),
 other_conditions:field("Delivery FREE; Delivery - FREE Wed, Nov 25; You'll get 12 month financing on this purchase.; By checking out, or buying with Apple Pay, you agree to Best Buy's Terms & Privacy Policy"),uncertainty_flags:['text_cut_off']},
 verdict:{decision:'WAIT',headline:'Sink hookup unconfirmed and cart is incomplete',confidence:'high'}};
(async()=>{
 const response=await new Promise(resolve=>handler({method:'POST',body:{pipeline,shopperGoal:'Wash small clothes loads using a sink connection',ownedTools:['Canva','ElevenLabs']}},{setHeader(){},status(code){assert.equal(code,200);return this;},json:resolve}));
 assert.equal(response.recommendation,null);
 assert.equal(response.ownedRecommendation,null);
 assert.deepEqual(response.otherCandidates,[]);
 assert.deepEqual(response.duplicates,[]);
 assert.deepEqual(response.pipelineVerdict,pipeline.verdict);
 assert.equal(response.noNewPurchase,false); // No library match is not a claim the washer isn't needed.
 console.log('PASS washer checkout has no unrelated AI recommendation; WAIT remains unchanged');
})().catch(e=>{console.error(e);process.exitCode=1;});
