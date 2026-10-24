/* Shuffle the order of tags within a parent tag. */

(function($){
  $.fn.shuffle = function() {
    return this.each(function(){
      var items = $(this).children();
      return (items.length)
        ? $(this).html($.shuffle(items))
        : this;
    });
  }

  $.shuffle = function(arr) {
    for(
      var j, x, i = arr.length; i;
      j = parseInt(Math.random() * i),
      x = arr[--i], arr[i] = arr[j], arr[j] = x
    );
    return arr;
  }
})(jQuery);

(function($) {
    $(function() {
        $('div.issues').shuffle();
        $('div.politicians').shuffle();
        $('div.front-party-logos').shuffle();
    });
}(jQuery));

// /* Cause link to 'where to vote' to pop-out. */
//
// (function($) {
//     $(function() {
//         $("a#where_to_vote").click(function(t){
//             t.preventDefault();
//             window.open("http://www.electionsmanitoba.ca/en/Voting/VotingInfo","myNewWin","width=500,height=500,toolbar=0,scrollbars=1")
//         });
//     });
// }(jQuery));
